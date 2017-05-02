# Battleship Client - author: Steve Hirabayashi
from socket import *
import sys
import os
import configparser
import json
from game import Game
from player import Player
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox

# Global variables
hostname = None
server_port = None
chat_port_min = None
configfile = 'client\conf\client.cfg'
configs = None
logfile = ""
recv_buffer = None

username = None
team = None
player_num = None

# GUI variables
TITLE_FONT = ("Helvetica", 18)
BODY_FONT = ("Helvetica", 12)
frame_size = {"small": "550x150", "medium": "600x520", "large": "1080x750"}

connection_socket = None  # TCP connection for request commands to server

# Keeps track of selected coordinates
ship_coords = { "carrier": [], "battleship": [], "cruiser": [], "submarine": [], "destroyer": []}
coords_taken = []
coords_complete = False

game_state = None
game_end = False
# Keeps track of players by username
players = {}


# Root GUI Window
class BattleshipApp(tk.Tk):
    titles = {"Connect": "Join Battleship Game",
              "Select": "Enter Username and Team Select",
              "Setup": "Place Your Ships",
              "Game": "Battleship"}
    def __init__(self):
        tk.Tk.__init__(self)
        self.geometry(frame_size["small"])

        # Menu
        menu_bar = tk.Menu(self)
        menu_bar.add_command(label="Rules", command=menu_rules)
        # create a help pulldown menu, and add it to the menu bar
        help_menu = tk.Menu(menu_bar, tearoff=0)
        help_menu.add_command(label="Setup", command=menu_setup)
        help_menu.add_command(label="Game", command=menu_game)
        help_menu.add_command(label="Chat", command=menu_chat)
        menu_bar.add_cascade(label="Help", menu=help_menu)

        menu_bar.add_command(label="Exit", command=self.quit)
        # display the menu
        self.config(menu=menu_bar)

        # The container represents stack of frames, visible frame will send to the top
        container = tk.Frame(self)
        container.pack(side="top", fill="both", expand=True)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        # Dictionary of each Frame part of the container
        self.frames = {"Connect": ConnectFrame(parent=container, controller=self),
                       "Select": SelectFrame(parent=container, controller=self),
                       "Setup": SetupFrame(parent=container, controller=self),
                       "Game": GameFrame(parent=container, controller=self)}

        self.frames["Connect"].grid(row=0, column=0, sticky="NSWE")
        self.frames["Select"].grid(row=0, column=0, sticky="NSWE")
        self.frames["Setup"].grid(row=0, column=0, sticky="NSWE")
        self.frames["Game"].grid(row=0, column=0, sticky="NSWE")

        self.show_frame("Connect")

    # Show a frame for the given page name
    def show_frame(self, page_name):
        frame = self.frames[page_name]
        frame.tkraise()

        if page_name == "Game":
            BattleshipApp.titles["Game"] = BattleshipApp.titles["Game"] + ' - ' + username + ' (Team ' + team + ')'
        self.title(BattleshipApp.titles[page_name])


# Messages to be displayed when selected from the menu
def menu_rules():
    rules = '''Battleship Rules:
    \nEach player is part of a team, and has their own 10 x 10 board where they place 5 ships horizontally or Vertically:
    Carrier (length of 5)
    Battleship (length of 4)
    Cruiser (length of 3)
    Submarine (length of 5)
    Destroyer (length of 2)
    \nEach team takes their turn once each game turn, for each player in a team, they get to shoot once per game turn.
    \nIf a shot hits, a HIT is displayed, otherwise a MISS is displayed.
    \nIf a shot hits a ship and all cells of the ship have been hit, The ship has been sunk and the type of ship sunk is displayed.
    \nIf all 5 ships of a player has been sunk, then that player is eliminated, if all players of a team have been eliminated, the team is also eliminated.
    \nThe game ends when only one team remains (not eliminated), they are the winners of the Battleship Game.'''
    messagebox.showinfo("Rules", rules)


def menu_setup():
    setup_msg = '''Joining a game:
    \nEnter a username and select a team color, afterwards wait for enough players to join in order to go to setup phase.
    \nGame Setup:
    \nYou are prompted to select the coordinates for your 5 ships. First, you select a coordinate that will represent the first endpoint of the ship.
    \nThen, you must select a coordinate that is N spaces away horizontally or vertically, where N is the length of the ship.
    \nShips cannot overlap previously taken coordinates that are reserved for other ships.
    \nOnce you select coordinates for all 5 ships, press the DONE button, and wait for all players to complete their board setup.'''
    messagebox.showinfo("Setup", setup_msg)


def menu_game():
    game_msg = '''Battleship Game:
    \nOn the upper left is the display of your board, on the upper right is the display of another player's board.
    \nIf you wish to see another player's (either ally or enemy team) board, select a player under the other board combobox and then press the OK button.
    \nBoard Color Representation:
    Gray = Not shot yet (allied board) / Unknown (enemy board)
    Colored = Allied ship un-hit position
    Red = Hit
    Dark Gray = Miss
    Black = Sunk ship
    \nStatus Text:
    \nOn the lower left text box, all game status messages will be displayed, displaying whose turn it is, moves of other players, elimination of players and teams, and any error messages for the user
    \nMaking a Move:
    \nSelect a cell in the other player's board to shoot that position; a move can only be made if:
    The player is still alive
    It is the player's turn
    The other player is on an enemy team
    The other player is still alive'''
    messagebox.showinfo("Setup", game_msg)


def menu_chat():
    chat_msg = '''Chat Feature:
        \nOn the lower right of the game window resides the chat box.
        Messages sent by you will be justified to the right
        while messages sent by everybody else will be justified to the left.
        Messages sent by each player will be color coded by the team
        that player is in.
        \nEntering a message:
        \nSend to ALL:
        This sends a message to every player.
        Select in the first combo box "ALL". Then enter your message in
        the bottom label and press ENTER.
        \nSend to ALLIES:
        This sends a message to your allied team players.
        Select in the first combo box "ALLIES".
        Then enter your message in the bottom label and press ENTER.
        \nSend to ENEMY:
        This sends a message to a given enemy team's players, as well as
        your allied team players.
        Select in the first combo box "ENEMY".
        Then select in the second combo box the enemy team you wish to
        send the message to.
        Then enter your message in the bottom label and press ENTER.'''
    messagebox.showinfo("Setup", chat_msg)


# First Frame, Connects to server
class ConnectFrame(tk.Frame):
    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        self.controller = controller

        welcome_label = tk.Label(self, text="Welcome to the Battleship Game", font=TITLE_FONT)
        welcome_label.pack(pady=15)

        connect_button = tk.Button(self, text="Join Game", width=15,
                              command=lambda: connect_server(controller))
        connect_button.pack(pady=10)


# Setup TCP connection with the server
def connect_server(controller):
    global connection_socket, player_num

    # Establish Control Connection (TCP)
    try:
        print_action('Attempting to connect to Battleship Server host: ' + hostname)
        connection_socket = socket(AF_INET, SOCK_STREAM)
        connection_socket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
        connection_socket.connect((hostname, server_port))

        conn_msg = connection_socket.recv(recv_buffer).decode()
        conn_tokens = conn_msg.split()
        print_action('\tServer Response:\n\t' + conn_msg)

        # Check if connection was accepted, otherwise end the client
        if conn_tokens[0] != 'SRDY':
            print_action('\nEnding Battleship Client Session')
            app.destroy()  # Forcibly close window
        else:
            player_num = int(conn_tokens[1])
    except (OSError, Exception) as e:
        connection_socket.close()
        print_action('Socket or Tkinter error: ' + str(e))
        app.destroy()  # Forcibly close window

    controller.show_frame("Select")


# Second Frame, Asks user for username and team color
class SelectFrame(tk.Frame):
    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        self.controller = controller

        # Prompt User for username and team color
        self.user = tk.StringVar()
        self.team_color = tk.StringVar()
        self.connect_msg = tk.StringVar()

        self.user_label = tk.Label(self, text="Enter Username:", font=BODY_FONT)
        self.user_label.grid(row=1, column=1, sticky='W', padx=20, pady=10)
        self.user_entry = tk.Entry(self, textvariable=self.user, width=35)
        self.user_entry.grid(row=1, column=2, sticky='W', padx=20, pady=10)

        self.team_label = tk.Label(self, text="Select Team:", font=BODY_FONT)
        self.team_label.grid(row=2, column=1, sticky='W', padx=20, pady=10)

        self.radioButtonFrame = tk.Frame(self)
        self.radioButtonFrame.grid(row=2, column=2, sticky='W', padx=20, pady=10)
        self.team_red_rbutton = tk.Radiobutton(self.radioButtonFrame, text="Red", fg="red", font=BODY_FONT,
                                               variable=self.team_color, value="Red")
        self.team_red_rbutton.grid(row=1, column=1)
        self.team_blue_rbutton = tk.Radiobutton(self.radioButtonFrame, text="Blue", fg="blue", font=BODY_FONT,
                                                variable=self.team_color, value="Blue")
        self.team_blue_rbutton.grid(row=1, column=2)
        self.team_green_rbutton = tk.Radiobutton(self.radioButtonFrame, text="Green", fg="green", font=BODY_FONT,
                                                 variable=self.team_color, value="Green")
        self.team_green_rbutton.grid(row=1, column=3)
        self.team_purple_rbutton = tk.Radiobutton(self.radioButtonFrame, text="Purple", fg="purple", font=BODY_FONT,
                                                  variable=self.team_color, value="Purple")
        self.team_purple_rbutton.grid(row=1, column=4)

        self.select_msg_label = tk.Label(self, textvariable=self.connect_msg, width=25, font=BODY_FONT)
        self.select_msg_label.grid(row=3, column=1, sticky='W', padx=5, pady=10)

        self.select_button = tk.Button(self, text="OK", width=15, command=lambda:
                                       send_user_and_team(controller, self.user.get(), self.team_color.get()))
        self.select_button.grid(row=3, column=2, sticky='E', padx=20, pady=10)


# Pass username and selected team to server
def send_user_and_team(controller, user, team_color):
    global username, team
    select_frame = controller.frames["Select"]
    # Send over Username and Team Color
    if user == "":
        select_frame.connect_msg.set("Error: Missing username")
        print_action("Error: Missing username")
    elif team_color == "":
        select_frame.connect_msg.set("Error: Have not selected a team")
        print_action("Error: Have not selected a team")
    else:
        username = user
        team = team_color
        select_frame.connect_msg.set("Waiting for other players to join")
        print_action("Entered: " + user + " " + team_color + "\nSuccessfully Joined Game, Waiting for other players")

        # Wait for all players to join
        app.after(100, wait_for_join_rdy, controller, user, team_color)


# Wait for all players to join
def wait_for_join_rdy(controller, user, team_color):
    connection_socket.send(("JOIN " + user + " " + team_color).encode())
    msg = connection_socket.recv(recv_buffer).decode()
    # All players have joined, go to game setup
    if msg == "OK":
        print_action("All Players have Joined, Go to Setup")
        app.geometry(frame_size["medium"])  # Resize and show setup frame
        controller.show_frame("Setup")
    elif msg == "WAIT":  # Send another request to server after 100ms
        app.after(100, wait_for_join_rdy, controller, user, team_color)
    else:  # Error in team setup
        print_action("Error: Team Setup Failure")
        connection_socket.close()
        app.destroy()  # Forcibly close window


# Third Frame, Asks user to place down their ships on their board
class SetupFrame(tk.Frame):
    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        self.controller = controller

        # Prompt User for ship coordinates
        self.select_msg = tk.StringVar()
        self.select_msg.set("Select first end coordinate for the carrier (length of 5)")
        self.select_input = tk.StringVar()
        self.select_input.set("Input: ")
        self.error_msg = tk.StringVar()

        self.current_ship = tk.StringVar()
        self.current_ship.set(Game.ships[0])
        self.select_first = tk.BooleanVar()  # Keeps track of selecting first end point or second end point
        self.select_first.set(True)

        self.setup_label = tk.Label(self, text="Select your Ship Positions", font=TITLE_FONT)
        self.setup_label.grid(row=1, column=1, padx=20, pady=10)

        self.select_grid_frame = tk.Frame(self)
        self.select_grid_frame.grid(row=2, column=1, padx=20, pady=10)

        self.buttons = []  # Store buttons in 2D list
        for row in range(11):
            if row > 0:
                self.buttons.append([])
            for col in range(11):
                if row == 0 and col == 0:
                    tk.Label(self.select_grid_frame, text="", font=BODY_FONT).grid(row=row, column=col)
                elif row == 0 and col in range(1, 11):
                    tk.Label(self.select_grid_frame, text=str(col), font=BODY_FONT).grid(row=row, column=col)
                elif row in range(1, 11) and col == 0:
                    tk.Label(self.select_grid_frame, text=Game.rows[row], font=BODY_FONT).grid(row=row, column=col)
                else:
                    button = tk.Button(self.select_grid_frame, text=(Game.rows[row] + str(col)), height=1, width=3)
                    button.grid(row=row, column=col)
                    button.configure(command=lambda row=row, col=col: press_coord(controller, row, col, self.current_ship))
                    self.buttons[row-1].append(button)

        self.display_frame = tk.Frame(self, borderwidth=4, relief="raised")
        self.display_frame.grid(row=3, column=1, padx=20, pady=10)
        self.select_msg_label = tk.Label(self.display_frame, textvariable=self.select_msg, font=BODY_FONT)
        self.select_msg_label.grid(row=1, column=1, padx=20, pady=5)

        self.error_msg_label = tk.Label(self.display_frame, textvariable=self.error_msg, font=BODY_FONT)
        self.error_msg_label.grid(row=2, column=1, padx=20, pady=5)

        self.setup_button = tk.Button(self.display_frame, text="", width=10, bg="dark gray")
        self.setup_button.grid(row=2, column=2, padx=20, pady=5)


def press_coord(controller, row, col, ship):
    global ship_coords, coords_taken, coords_complete
    if not coords_complete:
        setup_frame = controller.frames["Setup"]

        c_format = str(row) + "_" + str(col)
        coord = Game.rows[row] + str(col)
        if c_format in coords_taken:  # User selected a coordinate already occupied by a previous ship
            setup_frame.error_msg.set("Error: " + coord + " is already occupied")
        else:
            setup_frame.error_msg.set("")
            if setup_frame.select_first.get():  # Notify user of first button press for given ship
                ship_coords[ship.get()].append(c_format)
                setup_frame.select_msg.set("Select first end coordinate for the " + ship.get() +
                                           " (length of " + str(Game.ship_size[ship.get()]) + ") ")
                coords_taken.append(c_format)
                setup_frame.select_first.set(False)

                setup_frame.buttons[row - 1][col - 1].configure(bg=Game.ship_color[ship.get()])
            else:  # Second button pressed for given ship, confirm its a valid set of coordinates
                first_coord = ship_coords[ship.get()][0]
                gen_coords = generate_coords(ship, first_coord, c_format)
                if gen_coords:  # Store input coordinates for this ship, request for coordinates for next ship
                    for c in gen_coords:
                        ship_coords[ship.get()].append(c)
                        coords_taken.append(c)
                        c_tokens = c.split('_')
                        setup_frame.buttons[int(c_tokens[0])-1][int(c_tokens[1])-1].configure(
                            bg=Game.ship_color[ship.get()])

                    ship_index = Game.ships.index(ship.get())
                    if ship_index == len(Game.ships)-1:  # Got index of last ship, request user press DONE button
                        coords_complete = True  # Block user from entering anymore coordinates
                        setup_frame.select_msg.set("You have entered all ship coordinates, press DONE button")
                        # Change features of Done button to make it usable
                        setup_frame.setup_button.configure(text="DONE", bg="Light Gray",
                                                           command=lambda: send_ship_coords(controller))
                    else:
                        ship.set(Game.ships[ship_index+1])  # Update ship variable
                        setup_frame.select_first.set(True)
                        setup_frame.select_msg.set("Select first end coordinate for the " + ship.get() +
                                       " (length of " + str(Game.ship_size[ship.get()]) + ") ")

                else:  # Reset input coordinates for this ship
                    setup_frame.error_msg.set("Error: Invalid second endpoint for ship")
                    setup_frame.select_first.set(True)
                    setup_frame.select_msg.set("Select first end coordinate for the " + ship.get() +
                                   " (length of " + str(Game.ship_size[ship.get()]) + ") ")
                    # Clear saved coordinate for given ship
                    f_c_tokens = first_coord.split('_')
                    setup_frame.buttons[int(f_c_tokens[0]) - 1][int(f_c_tokens[1]) - 1].configure(bg="SystemButtonFace")
                    coords_taken.remove(first_coord)
                    ship_coords[ship.get()] = []


# Generate the coordinates of a ship, return empty list if the input is invalid
def generate_coords(ship, start_coord, end_coord):
    coords = []
    start = start_coord.split('_')
    end = end_coord.split('_')
    s_row = int(start[0])
    s_col = int(start[1])
    e_row = int(end[0])
    e_col = int(end[1])

    if s_row == e_row and abs(s_col - e_col) == Game.ship_size[ship.get()] - 1:  # Same row and right length
        if s_col < e_col:
            for y in range(s_col + 1, e_col + 1):
                new_coord = str(s_row) + '_' + str(y)
                if new_coord not in coords_taken:
                    coords.append(new_coord)
                else:
                    return []
        else:
            for y in range(e_col, s_col):
                new_coord = str(s_row) + '_' + str(y)
                if new_coord not in coords_taken:
                    coords.append(new_coord)
                else:
                    return []
    elif s_col == e_col and abs(s_row - e_row) == Game.ship_size[ship.get()] - 1:  # Same col and right length
        if s_row < e_row:
            for x in range(s_row + 1, e_row + 1):
                new_coord = str(x) + '_' + str(s_col)
                if new_coord not in coords_taken:
                    coords.append(new_coord)
                else:
                    return []
        else:
            for x in range(e_row, s_row):
                new_coord = str(x) + '_' + str(s_col)
                if new_coord not in coords_taken:
                    coords.append(new_coord)
                else:
                    return []
    else:  # Invalid coordinate endpoints or invalid length given
        return []
    return coords


def send_ship_coords(controller):
    print_action("User selected: " + str(ship_coords) + "\nSending coordinates to server")
    # Send over coordinates
    for ship in ship_coords:
        connection_socket.send((ship + " " + " ".join(ship_coords[ship])).encode())
        ok_msg = connection_socket.recv(recv_buffer).decode()
        if ok_msg != "OK":
            print_action("Error sending coords")
            connection_socket.close()
            app.destroy()

    setup_frame = controller.frames['Setup']
    setup_frame.select_msg.set('Coordinates saved\nWaiting for other players to choose ship locations')

    app.after(100, wait_for_setup_rdy, controller)


# Wait for all players to complete setup phase
def wait_for_setup_rdy(controller):
    connection_socket.send(("SETUP").encode())
    msg = connection_socket.recv(recv_buffer).decode()
    # All players have finished selecting coordinates, go to game setup
    if msg == "OK":
        print_action("All Players have Setup, Go to Game Start")
        receive_game_state(controller)
        init_game(controller)
        app.geometry(frame_size["large"])  # Resize and show game frame
        controller.show_frame("Game")
    elif msg == "WAIT":  # Send another request to server after 100ms
        app.after(100, wait_for_setup_rdy, controller)
    else:  # Error in team setup
        print_action("Error: Player Setup Failure")
        connection_socket.close()
        app.destroy()  # Forcibly close window


# Receive player, team, and board data
def receive_game_state(controller):
    global game_state

    connection_socket.send("SEND INFO".encode())

    print_action("Retrieving game state")
    json_string = connection_socket.recv(recv_buffer).decode()
    game_state = json.loads(json_string)  # Convert json string to game state dict

    print_action("Game state: " + str(game_state))
    print_action("Transfer Success")


# Setup the Game GUI to display initial data
def init_game(controller):
    global players
    game_frame = controller.frames["Game"]

    other_board_setup = False
    other_players = []
    for p_num in game_state["players"]:
        p_user, p_team = game_state[str(p_num)]
        players[p_user] = (p_num, p_team)  # Store players by username

        if p_user == username:  # Setup Player's board
            game_frame.your_label.configure(fg=p_team)
            for ship in ship_coords:
                for coord in ship_coords[ship]:
                    coord_tokens = coord.split('_')
                    game_frame.your_buttons[int(coord_tokens[0])-1][int(coord_tokens[1])-1].configure(bg=Game.ship_color[ship])
        else:
            other_players.append(p_user + " (" + p_team + ")")
            if not other_board_setup:
                game_frame.other_label.configure(text=(p_user + "'s Board"), fg=p_team)
                other_board_setup = True
    game_frame.board_combobox['values'] = tuple(other_players)  # Setup other player board combobox
    game_frame.board_combobox.current(0)

    other_teams = []
    for t in game_state['teams']:  # Setup chat combobox
        if t != team:
            other_teams.append(t)
    game_frame.send_to_combobox['values'] = tuple(other_teams)
    game_frame.send_to_combobox.current(0)

    game_frame.status_text.insert(tk.END, "[TURN 1] Current turn: Team " + game_state["first_turn"] + '\n',
                                  game_state["first_turn"])
    if game_state["first_turn"] == team:
        game_frame.status_text.insert(tk.END, "Waiting for your move\n", team)

    app.after(50, update_gui, controller)  # Begin constantly polling server for updates


# Fourth Frame, main game interface
class GameFrame(tk.Frame):
    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        self.controller = controller

        # Combo bar values
        self.board_cbox_value = tk.StringVar()
        self.chat_type_cbox_value = tk.StringVar()
        self.send_to_cbox_value = tk.StringVar()

        self.your_label = tk.Label(self, text="Your Board", font=TITLE_FONT)
        self.your_label.grid(row=1, column=1, padx=20, pady=10)

        self.your_grid_frame = tk.Frame(self)
        self.your_grid_frame.grid(row=2, column=1, padx=20, pady=10)

        self.your_buttons = []  # Store buttons in 2D list
        for row in range(11):
            if row > 0:
                self.your_buttons.append([])
            for col in range(11):
                if row == 0 and col == 0:
                    tk.Label(self.your_grid_frame, text="", font=BODY_FONT).grid(row=row, column=col)
                elif row == 0 and col in range(1, 11):
                    tk.Label(self.your_grid_frame, text=str(col), font=BODY_FONT).grid(row=row, column=col)
                elif row in range(1, 11) and col == 0:
                    tk.Label(self.your_grid_frame, text=Game.rows[row], font=BODY_FONT).grid(row=row, column=col)
                else:
                    button = tk.Button(self.your_grid_frame, text="", height=1, width=3)
                    button.grid(row=row, column=col)
                    self.your_buttons[row - 1].append(button)

        self.other_label = tk.Label(self, text="Other Board", font=TITLE_FONT)
        self.other_label.grid(row=1, column=2, padx=20, pady=10)

        self.other_grid_frame = tk.Frame(self)
        self.other_grid_frame.grid(row=2, column=2, padx=20, pady=10)

        self.other_buttons = []  # Store buttons in 2D list
        for row in range(11):
            if row > 0:
                self.other_buttons.append([])
            for col in range(11):
                if row == 0 and col == 0:
                    tk.Label(self.other_grid_frame, text="", font=BODY_FONT).grid(row=row, column=col)
                elif row == 0 and col in range(1, 11):
                    tk.Label(self.other_grid_frame, text=str(col), font=BODY_FONT).grid(row=row, column=col)
                elif row in range(1, 11) and col == 0:
                    tk.Label(self.other_grid_frame, text=Game.rows[row], font=BODY_FONT).grid(row=row, column=col)
                else:
                    button = tk.Button(self.other_grid_frame, text="", height=1, width=3,
                                       command=lambda row=row, col=col: make_move(controller, row, col))
                    button.grid(row=row, column=col)
                    self.other_buttons[row - 1].append(button)

        self.change_board_frame = tk.Frame(self)  # Change what other board displays
        self.change_board_frame.grid(row=3, column=2, sticky='WE', padx=20, pady=5)
        self.board_cbox_label = tk.Label(self.change_board_frame, text="Select Display of Other Board: ", font=BODY_FONT)
        self.board_cbox_label.grid(row=1, column=1, sticky='W', padx=5)
        self.board_combobox = ttk.Combobox(self.change_board_frame, width=25, textvariable=self.board_cbox_value,
                                           state='readonly')
        self.board_combobox.grid(row=1, column=2, sticky='W', padx=5)
        self.board_button = tk.Button(self.change_board_frame, text="OK", width=5,
                                      command=lambda: update_other_board(controller))
        self.board_button.grid(row=1, column=3, sticky='W', padx=5)

        self.status_frame = tk.Frame(self, borderwidth=4, relief="raised")  # Store game state messages
        self.status_frame.grid(row=4, column=1, sticky='NWS', padx=10, pady=10)

        self.status_label = tk.Label(self.status_frame, text="Game Status", font=BODY_FONT)
        self.status_label.grid(row=1, column=1, sticky='W', padx=10, pady=10)

        self.status_text = tk.Text(self.status_frame, height=12, width=50, font=BODY_FONT)
        self.status_text.bind("<Key>", lambda e: "break")  # Set as read-only for user
        # Set chat text options
        self.status_text.tag_configure("Red", foreground="red")
        self.status_text.tag_configure("Blue", foreground="blue")
        self.status_text.tag_configure("Green", foreground="green")
        self.status_text.tag_configure("Purple", foreground="purple")
        self.status_text.grid(row=2, column=1, sticky='E', padx=5, pady=5)
        self.status_scrollbar = tk.Scrollbar(self.status_frame, command=self.status_text.yview)
        self.status_scrollbar.grid(row=2, column=2, sticky='NWS', padx=5, pady=5)
        self.status_text.configure(yscrollcommand=self.status_scrollbar.set)

        self.chat_frame = tk.Frame(self, borderwidth=4, relief="raised")  # Store chat log
        self.chat_frame.grid(row=4, column=2, rowspan=2, sticky='NES', padx=20, pady=10)

        self.chat_label = tk.Label(self.chat_frame, text="Chat", font=BODY_FONT)
        self.chat_label.grid(row=1, column=1, sticky='W', padx=10, pady=10)

        self.chat_text = tk.Text(self.chat_frame, height=8, width=54, font=BODY_FONT)
        self.chat_text.bind("<Key>", lambda e: "break")  # Set as read-only for user
        # Set chat text options
        self.chat_text.tag_configure("player-Red", justify="right", foreground="red")
        self.chat_text.tag_configure("player-Blue", justify="right", foreground="blue")
        self.chat_text.tag_configure("player-Green", justify="right", foreground="green")
        self.chat_text.tag_configure("player-Purple", justify="right", foreground="purple")
        self.chat_text.tag_configure("other-Red", justify="left", foreground="red")
        self.chat_text.tag_configure("other-Blue", justify="left", foreground="blue")
        self.chat_text.tag_configure("other-Green", justify="left", foreground="green")
        self.chat_text.tag_configure("other-Purple", justify="left", foreground="purple")

        self.chat_text.grid(row=2, column=1, sticky='W', padx=5)
        self.chat_scrollbar = tk.Scrollbar(self.chat_frame, command=self.chat_text.yview)
        self.chat_scrollbar.grid(row=2, column=2, sticky='NWS', padx=5)
        self.chat_text.configure(yscrollcommand=self.chat_scrollbar.set)

        self.chat_enter_frame = tk.Frame(self.chat_frame)
        self.chat_enter_frame.grid(row=3, column=1, sticky='W', pady=10)

        self.chat_type_combobox = ttk.Combobox(self.chat_enter_frame, width=5, textvariable=self.chat_type_cbox_value,
                                               values=("ALL", "ALLIES", "ENEMY"), state='readonly')
        self.chat_type_combobox.current(0)
        self.chat_type_combobox.grid(row=1, column=1, sticky='WE', padx=5, pady=5)
        self.send_to_combobox = ttk.Combobox(self.chat_enter_frame, width=5, textvariable=self.send_to_cbox_value,
                                             state='readonly')
        self.send_to_combobox.grid(row=1, column=2, sticky='WE', pady=5)
        self.chat_input_text = tk.Text(self.chat_enter_frame, height=1, width=40, font=BODY_FONT)
        self.chat_input_text.grid(row=1, column=3, sticky='WE', padx=5, pady=5)
        self.chat_button = tk.Button(self.chat_enter_frame, text="Enter", width=10,
                                     command=lambda: add_to_chat(controller))
        self.chat_button.grid(row=2, column=3, sticky='E', padx=5, pady=5)


def update_gui(controller):
    global game_end
    game_frame = controller.frames["Game"]

    # UPDATE 1 (MOVES)
    connection_socket.send("UPDATE_GAME".encode())
    game_msg = connection_socket.recv(recv_buffer).decode()

    if game_msg == "UPDATE":
        board_selected_tokens = game_frame.board_cbox_value.get().split()
        other_board_username = board_selected_tokens[0]

        connection_socket.send("OK".encode())
        # Receive each state notification
        joined_state_list = connection_socket.recv(recv_buffer).decode()
        state_list = joined_state_list.split('\n')
        token_list = []

        for state_msg in state_list:  # Add state message to state textbox, change display of boards accordingly
            state_tokens = state_msg.split()
            if state_tokens[0] == "HIT":
                token_list.append("HIT")
                attacker_username = state_tokens[1]
                attacker_num, attacker_team = players[attacker_username]
                defender_username = state_tokens[2]
                row = int(state_tokens[3])
                col = int(state_tokens[4])

                game_frame.status_text.insert(tk.END, attacker_username + " HIT " + defender_username + "'s ship at " +
                                              Game.rows[row] + str(col) + '\n', attacker_team)
                game_frame.status_text.see(tk.END)
                if defender_username == username:  # Update user's board
                    game_frame.your_buttons[row-1][col-1].configure(bg=Game.move_markers["HIT"])
                elif defender_username == other_board_username:  # Update other player's board
                    game_frame.other_buttons[row-1][col-1].configure(bg=Game.move_markers["HIT"])

            elif state_tokens[0] == "MISS":
                token_list.append("MISS")
                attacker_username = state_tokens[1]
                attacker_num, attacker_team = players[attacker_username]
                defender_username = state_tokens[2]
                row = int(state_tokens[3])
                col = int(state_tokens[4])

                game_frame.status_text.insert(tk.END, attacker_username + " MISSED shooting " + defender_username +
                                              " at " + Game.rows[row] + str(col) + '\n', attacker_team)
                game_frame.status_text.see(tk.END)
                if defender_username == username:  # Update user's board
                    game_frame.your_buttons[row - 1][col - 1].configure(bg=Game.move_markers["MISS"])
                elif defender_username == other_board_username:  # Update other player's board
                    game_frame.other_buttons[row - 1][col - 1].configure(bg=Game.move_markers["MISS"])

            elif state_tokens[0] == "SUNK":
                token_list.append("SUNK")
                attacker_username = state_tokens[1]
                attacker_num, attacker_team = players[attacker_username]
                defender_username = state_tokens[2]
                ship = state_tokens[3]

                game_frame.status_text.insert(tk.END, attacker_username + " SUNK " + defender_username +
                                              "'s " + ship + '\n', attacker_team)
                game_frame.status_text.see(tk.END)
                # process coordinates
                for coord in state_tokens[4:]:
                    coords = coord.split('_')
                    row = int(coords[0]) - 1
                    col = int(coords[1]) - 1
                    if defender_username == username:  # Update user's board
                        game_frame.your_buttons[row][col].configure(bg=Game.move_markers["SUNK"])
                    elif defender_username == other_board_username:  # Update other player's board
                        game_frame.other_buttons[row][col].configure(bg=Game.move_markers["SUNK"])

            elif state_tokens[0] == "ELIM_PLAYER":
                token_list.append("ELIM_PLAYER")
                attacker_username = state_tokens[1]
                attacker_num, attacker_team = players[attacker_username]
                defender_username = state_tokens[2]

                game_frame.status_text.insert(tk.END, attacker_username + " has ELIMINATED " + defender_username + '\n',
                                              attacker_team)
                game_frame.status_text.see(tk.END)

            elif state_tokens[0] == "ELIM_TEAM":
                token_list.append("ELIM_TEAM")
                game_frame.status_text.insert(tk.END, "Team " + state_tokens[1] + " has ELIMINATED Team " +
                                              state_tokens[2] + '\n', state_tokens[1])
                game_frame.status_text.see(tk.END)

            elif state_tokens[0] == "GAME_END":
                token_list.append("GAME_END")
                game_frame.status_text.insert(tk.END, "Game has Ended. The winners are Team " + state_tokens[1] + '!\n',
                                              state_tokens[1])
                game_frame.status_text.see(tk.END)
                game_end = True

            elif state_tokens[0] == "TURN_CHANGE":
                token_list.append("TURN_CHANGE")
                game_frame.status_text.insert(tk.END, "[TURN " + str(state_tokens[1]) + "] Current turn: Team " +
                                              state_tokens[2] + '\n', state_tokens[2])
                game_frame.status_text.see(tk.END)
                if state_tokens[2] == team:
                    game_frame.status_text.insert(tk.END, "\tWaiting for your move\n", team)
                    game_frame.status_text.see(tk.END)
        print_action("Updated Game " + str(token_list))


    # UPDATE 2 (CHAT LOG)
    connection_socket.send("UPDATE_CHAT".encode())
    update_msg = connection_socket.recv(recv_buffer).decode()

    if update_msg == "UPDATE":
        # Create chat socket, send address to server
        try:
            chat_socket = socket(AF_INET, SOCK_DGRAM)
            chat_socket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
            host = gethostname()
            host_address = gethostbyname(host)
            chat_socket.bind((host_address, chat_port_min + player_num))

            connection_socket.send(host_address.encode())  # Send over client address
            chat_msg = ""
            chat_list = []
            while True:  # Receive each chat message that needs to be appended to chat log
                if chat_msg == "SEND COMPLETE":
                    break
                else:
                    chat_msg, srv_addr = chat_socket.recvfrom(recv_buffer)
                    chat_msg = chat_msg.decode()
                    if chat_msg != "SEND COMPLETE":
                        chat_list.append(chat_msg)

            ok_msg = connection_socket.recv(recv_buffer).decode()
            chat_socket.close()
        except OSError as e:
            connection_socket.close()
            print_action("Socket error: " + str(e))
            sys.exit(1)

        for msg in chat_list:
            # Determine writer of message
            chat_tokens = msg.split()
            user = chat_tokens[0][1:]
            p_num, p_team = players[user]
            # Update chat
            if p_num == player_num:
                game_frame.chat_text.insert(tk.END, msg, 'player-' + p_team)
            else:
                game_frame.chat_text.insert(tk.END, msg, 'other-' + p_team)
            game_frame.chat_text.see(tk.END)
            print_action("Updated chat message: " + msg.strip('\n'))

    if not game_end:
        app.after(50, update_gui, controller)
    else:  # Send Terminating Command
        connection_socket.send("END_GAME".encode())
        end_msg = connection_socket.recv(recv_buffer).decode()
        # TODO: END GAME DIALOG
        print_action("\nClosing Battleship Game Client")
        game_frame.status_text.insert(tk.END, "Closing window in 15 seconds...")
        game_frame.status_text.see(tk.END)
        app.after(15000, close_app)


def make_move(controller, row, col):
    if not game_end:
        game_frame = controller.frames["Game"]
        board_selected_tokens = game_frame.board_cbox_value.get().split()
        defender_num, defender_team = players[board_selected_tokens[0]]
        if defender_team == team:  # Guard against friendly fire
            game_frame.status_text.insert(tk.END, "ERROR: Can't shoot allied player\n")
            game_frame.status_text.see(tk.END)
        else:
            connection_socket.send(("MOVE " + str(defender_num) + ' ' + str(row) + ' ' + str(col)).encode())
            print_action("Sent move: " + board_selected_tokens[0] + ' ' + str(row) + ' ' + str(col))
            move_msg = connection_socket.recv(recv_buffer).decode()
            if move_msg == "NOT_YOUR_TURN":
                game_frame.status_text.insert(tk.END, "ERROR: It is not your turn\n")
                game_frame.status_text.see(tk.END)
            elif move_msg == "ALREADY_TAKEN_TURN":
                game_frame.status_text.insert(tk.END, "ERROR: You have already taken your turn\n")
                game_frame.status_text.see(tk.END)
            elif move_msg == "YOU_ARE_DEAD":
                game_frame.status_text.insert(tk.END, "ERROR: You are eliminated\n")
                game_frame.status_text.see(tk.END)
            elif move_msg == "ENEMY_IS_DEAD":
                game_frame.status_text.insert(tk.END, "ERROR: " + board_selected_tokens[0] + " is already dead\n")
                game_frame.status_text.see(tk.END)


def update_other_board(controller):
    if not game_end:
        game_frame = controller.frames["Game"]
        board_selected_tokens = game_frame.board_cbox_value.get().split()
        other_num, other_team = players[board_selected_tokens[0]]

        current_other_user = game_frame.other_label.cget("text").split("'")
        if current_other_user[0] != board_selected_tokens[0]:  # Skip update if current board is same as user choice
            if other_team == team:
                connection_socket.send(("NEW_BOARD " + str(other_num) + ' ' + "ALLY").encode())
                grid_msg = connection_socket.recv(recv_buffer).decode()
                connection_socket.send("SHIP_COORDS".encode())  # Request for ship coordinates
                json_ship = connection_socket.recv(recv_buffer).decode()
                ship_coords = json.loads(json_ship)  # Convert json string to ship coords dict

                grid_rows = grid_msg.split('\n')  # Un-package the string back to a 2D list
                for row in range(1, 11):
                    cols = grid_rows[row].split()
                    for col in range(1, 11):
                        if cols[col] == Player.c_state["Empty"]:
                            game_frame.other_buttons[row-1][col-1].configure(bg=Game.move_markers["DEFAULT"])
                        elif cols[col] == Player.c_state["Hit"]:
                            game_frame.other_buttons[row-1][col-1].configure(bg=Game.move_markers["HIT"])
                        elif cols[col] == Player.c_state["Miss"]:
                            game_frame.other_buttons[row-1][col-1].configure(bg=Game.move_markers["MISS"])
                        elif cols[col] == Player.c_state["Sunk"]:
                            game_frame.other_buttons[row-1][col-1].configure(bg=Game.move_markers["SUNK"])
                # Run through ship coordinates for their specific ship colors
                for ship in ship_coords:
                    for coord in ship_coords[ship]:
                        coord_tokens = coord.split('_')
                        game_frame.other_buttons[int(coord_tokens[0])-1][int(coord_tokens[1])-1].configure(
                            bg=Game.ship_color[ship])

            else:
                connection_socket.send(("NEW_BOARD " + str(other_num) + ' ' + "ENEMY").encode())
                grid_msg = connection_socket.recv(recv_buffer).decode()

                grid_rows = grid_msg.split('\n')  # Un-package the string back to a 2D list
                for row in range(1, 11):
                    cols = grid_rows[row].split()
                    for col in range(1, 11):
                        if cols[col] == Player.c_state["Hit"]:
                            game_frame.other_buttons[row-1][col-1].configure(bg=Game.move_markers["HIT"])
                        elif cols[col] == Player.c_state["Miss"]:
                            game_frame.other_buttons[row-1][col-1].configure(bg=Game.move_markers["MISS"])
                        elif cols[col] == Player.c_state["Sunk"]:
                            game_frame.other_buttons[row-1][col-1].configure(bg=Game.move_markers["SUNK"])
                        else:
                            game_frame.other_buttons[row-1][col-1].configure(bg=Game.move_markers["DEFAULT"])

            # Update board label
            game_frame.other_label.configure(text=(board_selected_tokens[0] + "'s Board"), fg=other_team)
            print_action("Updated board display: " + board_selected_tokens[0])


def add_to_chat(controller):
    if not game_end:
        game_frame = controller.frames["Game"]
        # Send notification of wanting to send chat message
        if game_frame.chat_type_cbox_value.get() == "ENEMY":
            connection_socket.send(("CHAT ENEMY " + game_frame.send_to_cbox_value.get() + ' ' + team).encode())
        else:
            connection_socket.send(("CHAT " + game_frame.chat_type_cbox_value.get()).encode())

        # Create chat socket
        try:
            chat_socket = socket(AF_INET, SOCK_DGRAM)
            chat_socket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
            #  Wait for socket to be created in server
            send_msg = connection_socket.recv(recv_buffer).decode()

            # Send the chat message over to the server
            chat_socket.sendto(game_frame.chat_input_text.get("1.0", tk.END).encode(), (hostname, chat_port_min + player_num))
            chat_socket.close()
        except OSError as e:
            connection_socket.close()
            print_action("Socket error: " + str(e))
            sys.exit(1)
        # Clear the chat input box
        print_action("Sent chat message: " + game_frame.chat_input_text.get("1.0", tk.END).strip('\n'))
        game_frame.chat_input_text.delete("1.0", tk.END)
        ok_msg = connection_socket.recv(recv_buffer).decode()


def configure():
    global hostname, server_port, chat_port_min, configfile, configs, logfile, recv_buffer

    configfile = get_pathname(configfile)
    if not os.path.exists(configfile):
        print("Error: Could not find config file. Exiting...")
        sys.exit(1)
    configs = configparser.ConfigParser()
    configs.read(configfile)

    hostname = configs['CLIENT']['HOST_NAME']
    server_port = int(configs['CLIENT']['SERVER_PORT'])
    chat_port_min = int(configs['CLIENT']['CHAT_PORT_MIN'])

    logfile = get_pathname(configs['CLIENT']['PATH_LOG'])
    if not os.path.exists(logfile):
        print("Error: log file not found. Exiting...")
        sys.exit(1)

    recv_buffer = int(configs['CLIENT']['RECV_BUFFER'])


def print_action(msg):
    print(msg)
    with open(logfile, "at") as f_log:
        f_log.write(msg + '\n')


# Convert pathname to correct pathname
def get_pathname(pathname, cwd=os.getcwd()):
    path = cwd
    pathname = pathname.replace('\\', '/')
    files = pathname.split('/')
    for dir in files:
        if dir is not None:
            path = os.path.join(path, dir)
    return os.path.normpath(path)


# Terminate the client
def close_app():
    connection_socket.close()
    app.quit()


if __name__ == "__main__":
    # Configure the program based on configuration file
    configure()
    # Open log file to begin writing
    f_log = open(logfile, 'wt')
    f_log.write('Beginning Battleship Client Session\n')
    f_log.close()
    print('Beginning Battleship Client Session')

    app = BattleshipApp()
    app.mainloop()