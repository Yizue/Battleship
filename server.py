# Battleship Server - author: Steve Hirabayashi
from socket import *
import threading
import sys
import os
import configparser
import json
from player import Player
from game import Game

# Globals
thread_list = []
hostname = None
server_port = None
chat_port_min = None
configfile = 'server\conf\server.cfg'
configs = None
logfile = None
max_players = None
users = {}
root = ""
recv_buffer = None

game = None  # Holds the current game state

game_lock = threading.Lock()  # Lock for processing game state
log_lock = threading.Lock()  # Lock for writing to logfile

abort_game = False


# Setup the server using the configuration file
def configure():
    global hostname, server_port, chat_port_min, configfile, configs, logfile, max_players, recv_buffer, \
           game, player_ready_count

    configfile = get_pathname(configfile)
    # Retrieve default settings from configuration file, store into configs dict
    if not os.path.exists(configfile):
        print("Error: Could not find config file. Exiting...")
        sys.exit(1)
    configs = configparser.ConfigParser()
    configs.read(configfile)

    hostname = configs['SERVER']['HOST_NAME']
    server_port = int(configs['SERVER']['SERVER_PORT'])
    chat_port_min = int(configs['SERVER']['CHAT_PORT_MIN'])

    logfile = get_pathname(configs['SERVER']['PATH_LOG'])
    if not os.path.exists(logfile):
        print("Error: Could not find log file. Exiting...")
        sys.exit(1)

    max_players = int(configs['SERVER']['MAX_PLAYERS'])
    recv_buffer = int(configs['SERVER']['RECV_BUFFER'])
    # Initialize Game state
    game = Game(max_players)


def main():
    global thread_list, game, abort_game
    # Configure the program based on configuration file
    configure()

    # Open log file to begin writing
    f_log = open(logfile, 'wt')
    f_log.write('Starting the Battleship Server\n')
    f_log.close()

    # Create Server Socket (TCP)
    server_socket = socket(AF_INET, SOCK_STREAM)
    server_socket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
    server_socket.bind((hostname, server_port))
    server_socket.listen(5)
    print_action('The Battleship Server is ready')

    # Receiving TCP connection from players
    while not threading.active_count() - 1 == max_players:
        try:
            connection_socket, addr = server_socket.accept()
            # Check if at the maximum connection limit
            if threading.active_count() - 1 <= max_players:
                # Assign a player number to this player
                player_num = game.assign_player_num()
                # Send Confirmation Message and player num
                connection_socket.send(('SRDY ' + str(player_num)).encode())
                print_action('Sent: SRDY ' + str(player_num))

                print_action("*** Thread client entering now for: " + str(addr) + " ***")

                # Create and start thread for player
                t = threading.Thread(target=client_thread, args=(connection_socket, addr, player_num))
                t.start()
                thread_list.append(t)
            else:
                # Send Error message
                connection_socket.send('BUSY Battleship game is full, please try again later'.encode())
                print_action('Sent: BUSY Battleship game is full, please try again later')
        except OSError as e:
            print_action("Socket error: " + str(e))
            sys.exit(1)

    # Check if game is ready to launch
    while not game.game_setup:
        game_lock.acquire()
        if game.player_join_count == max_players:
            if game.enough_teams():
                print_action("Teams ready, Going to game setup")
                game.game_setup = True
            else:
                print_action("Not enough teams, cancelling game")
                # TODO: RESET TEAM OPTION
                sys.exit(1)
        game_lock.release()

    # Wait until everyone has finished entering their ship coordinates
    while not game.game_start:
        game_lock.acquire()
        if game.player_ready_count == max_players:
            print_action("Game setup complete, beginning game")
            game.game_start = True
            # Randomly designate first team
            game.select_first_team()
        game_lock.release()

    # Keep game going until game terminates
    while not game.game_end:
        pass

    print_action("The game has ended.\nThe winning team is: " + game.team_winner)

    # Close server socket
    server_socket.close()
    for t in thread_list:
        t.join()
    print_action("Closing the Battleship Server")
    sys.exit(0)


def client_thread(connection_socket, addr, player_num):
    global game
    # Get username and team choice, send designated player number
    # Wait for game to enter setup phase
    while True:
        msg_tokens = connection_socket.recv(recv_buffer).decode().split()
        username = msg_tokens[1]
        team = msg_tokens[2]

        game_lock.acquire()
        if game.player_join_count < max_players:
            if player_num not in list(game.players.keys()):
                game.add_player(Player(username, team, player_num), player_num)
                game.add_team(team, player_num)
                game.player_join_count += 1
        game_lock.release()

        if game.game_setup:
            # Notify client game setup phase has started
            connection_socket.send("OK".encode())
            break
        else:
            connection_socket.send("WAIT".encode())

    # Receive ship locations from player
    process_coordinates(connection_socket, player_num)
    game_lock.acquire()
    game.player_ready_count += 1
    game_lock.release()

    # Wait for game to start
    while True:
        msg_tokens = connection_socket.recv(recv_buffer).decode().split()
        if game.game_start:
            # Notify client game start phase has started
            connection_socket.send("OK".encode())
            break
        else:
            connection_socket.send("WAIT".encode())

    # Send to client the players, teams, and their initial board states
    send_msg = connection_socket.recv(recv_buffer).decode()
    if send_msg == "SEND INFO":
        send_initial_game_state(connection_socket, player_num)
    else:
        connection_socket.close()
        print_action("Error: Bad request for game information")
        sys.exit(1)

    while game.player_end_count < max_players:
        # Receive requests from client and respond to them
        run_cmds(connection_socket, addr, player_num)

    print_action("*** Thread closed for: " + str(addr) + " ***")
    # Close control socket
    connection_socket.close()


# Receive and execute action commands from player
def run_cmds(connection_socket, addr, player_num):
    global game
    player = game.get_player(player_num)

    cmd_msg = connection_socket.recv(recv_buffer).decode()
    tokens = cmd_msg.split()

    if tokens[0] == "UPDATE_GAME":
        # Check if game state for player needs to be sent
        state_list = player.get_state_buffer()
        if state_list:
            connection_socket.send("UPDATE".encode())
            ok_msg = connection_socket.recv(recv_buffer).decode()
            connection_socket.send(('\n'.join(state_list)).encode())
            print_action('Sent state messages to: ' + str(player_num))

            game_lock.acquire()
            player.clear_state_buffer()  # Clear the state buffer
            game_lock.release()
        else:
            connection_socket.send("GAME OK".encode())

    elif tokens[0] == "UPDATE_CHAT":
        # Check if chat messages need to be sent
        chat_list = player.get_chat_messages()
        if chat_list:
            connection_socket.send("UPDATE".encode())
            client_addr = connection_socket.recv(recv_buffer).decode()  # Wait for chat socket to be created
            # setup chat connection (UDP) and send over the chat messages
            try:
                chat_socket = socket(AF_INET, SOCK_DGRAM)
                for chat_msg in chat_list:  # send messages to the server socket
                    chat_socket.sendto(chat_msg.encode(), (client_addr, chat_port_min + player_num))
                chat_socket.sendto("SEND COMPLETE".encode(), (client_addr, chat_port_min + player_num))
                chat_socket.close()
            except OSError as e:
                connection_socket.close()
                print_action("Socket error: " + str(e))
                sys.exit(1)

            connection_socket.send("OK".encode())
            print_action("Sent chat messages to: " + str(player_num))

            game_lock.acquire()
            player.clear_chat_messages()
            game_lock.release()
        else:  # Chat buffer empty, no changes need to be made
            connection_socket.send("CHAT OK".encode())

    elif tokens[0] == "NEW_BOARD":  # Requesting for updating other board
        other_num = int(tokens[1])
        if tokens[2] == "ALLY":
            connection_socket.send((game.players[other_num].get_grid()).encode())
            ship_msg = connection_socket.recv(recv_buffer).decode()
            # Serialize the ship coordinates into JSON string
            json_string = json.dumps(game.players[other_num].get_ship_coordinates())  # Data serialized
            connection_socket.send(json_string.encode())
        elif tokens[2] == "ENEMY":
            connection_socket.send((game.players[other_num].get_grid()).encode())
        print_action("Sent new board to: " + str(player_num))

    elif tokens[0] == "MOVE":  # Entering a move
        defender = game.get_player(int(tokens[1]))
        row = int(tokens[2])
        col = int(tokens[3])
        # Verify if it's this player's turn and both players are alive
        if player.team == game.team_turn and not player.taken_turn and player.is_alive and defender.is_alive:
            game_lock.acquire()
            game.make_move(player, defender, row, col)
            game_lock.release()
            print_action("Received move from: " + str(player_num) + ": " + tokens[1] + ' ' +
                         tokens[2] +'_' + tokens[3])
            connection_socket.send("MOVE_OK".encode())
        elif not player.is_alive:
            connection_socket.send("YOU_ARE_DEAD".encode())
        elif not defender.is_alive:
            connection_socket.send("ENEMY_IS_DEAD".encode())
        elif player.taken_turn and player.team == game.team_turn:
            connection_socket.send("ALREADY_TAKEN_TURN".encode())
        else:
            connection_socket.send("NOT_YOUR_TURN".encode())

    elif tokens[0] == "CHAT":  # Entering a chat message
        # Create UDP socket
        try:
            chat_socket = socket(AF_INET, SOCK_DGRAM)
            chat_socket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
            chat_socket.bind((hostname, chat_port_min + player_num))
            connection_socket.send("SEND MSG".encode())  # Notify client UDP socket created
            # Receive and store chat message
            chat_msg, address = chat_socket.recvfrom(recv_buffer)
            chat_msg = chat_msg.decode()
            chat_socket.close()
        except OSError as e:
            print_action("Socket error: " + str(e))
            connection_socket.close()
            sys.exit(1)
        # Determine chat receivers, chat types = ALL, TEAM, ENEMY, PLAYER
        if tokens[1] == "ALL":
            for player_num in game.players:
                game_lock.acquire()
                game.players[player_num].add_chat_message("[" + player.username + " (ALL)] " + chat_msg)
                game_lock.release()
        elif tokens[1] == "ALLIES":  # Your Team
            for player_num in game.teams[player.team]:
                game_lock.acquire()
                game.players[player_num].add_chat_message("[" + player.username + " (ALLIES)] " + chat_msg)
                game_lock.release()
        elif tokens[1] == "ENEMY":  # An Enemy Team (send also to sender's team)
            for player_num in game.teams[tokens[2]]:
                game_lock.acquire()
                game.players[player_num].add_chat_message("[" + player.username + " (FROM ENEMY - " + tokens[2] + ")] "
                                                          + chat_msg)
                game_lock.release()
            for player_num in game.teams[tokens[3]]:
                game_lock.acquire()
                game.players[player_num].add_chat_message("[" + player.username + " (TO ENEMY - " + tokens[2] + ")] "
                                                          + chat_msg)
                game_lock.release()
        print_action("Received Chat message from: " + str(player_num) + ": " + chat_msg.strip('\n'))
        connection_socket.send("CHAT OK".encode())

    elif tokens[0] == "END_GAME":
        game.player_end_count += 1
        connection_socket.send("OK".encode())
    else:
        connection_socket.send("UNKNOWN CODE".encode())  # Can't identify code


def print_action(msg):
    log_lock.acquire()
    print(msg)
    with open(logfile, "at") as f_log:
        f_log.write(msg + '\n')
    log_lock.release()


# Convert pathname to correct pathname
def get_pathname(pathname, cwd=os.getcwd()):
    path = cwd
    pathname = pathname.replace('\\', '/')
    files = pathname.split('/')
    for dir in files:
        if dir is not None:
            path = os.path.join(path, dir)
    return os.path.normpath(path)


def process_coordinates(connection_socket, player_num):
    global game
    player = game.get_player(player_num)
    ship_coords = {"carrier": "", "battleship": "", "cruiser": "", "submarine": "", "destroyer": ""}
    for ship in ship_coords:
        coord_tokens = connection_socket.recv(recv_buffer).decode().split()
        print_action("Received from " + str(player_num) + ": " + str(coord_tokens))

        game_lock.acquire()
        player.set_ship_coordinates(coord_tokens[0], coord_tokens[1:])
        for coord in coord_tokens[1:]:
            c_tokens = coord.split('_')
            player.set_grid_coordinate(int(c_tokens[0]), int(c_tokens[1]), Player.c_state["Ship"])
        game_lock.release()

        connection_socket.send("OK".encode())


# Send the game object as a json string to the client
def send_initial_game_state(connection_socket, player_num):
    game_state = {"players": list(game.players.keys()),
                  "teams": game.teams,
                  "first_turn": game.first_team_turn}
    for player_num in game_state["players"]:
        player = game.get_player(player_num)
        player_data = {str(player_num): (player.username, player.team)}
        game_state.update(player_data)

    # Serialize the players and teams into a json string
    json_string = json.dumps(game_state)  # Data serialized
    connection_socket.send(json_string.encode())  # Data sent over
    print_action("Sent initial game state to: " + str(player_num) + ' ' + str(sys.getsizeof(json_string.encode()))
                 + ' bytes')


if __name__ == "__main__":
    main()
