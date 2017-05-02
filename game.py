# Game - object represents the current game state
import random

class Game():
    # Static Variables
    ships = ["carrier", "battleship", "cruiser", "submarine", "destroyer"]
    ship_size = {"carrier": 5, "battleship": 4, "cruiser": 3, "submarine": 3, "destroyer": 2}
    ship_color = {"carrier": "cyan", "battleship": "green", "cruiser": "purple", "submarine": "blue", "destroyer": "yellow"}
    team_colors = ["Red", "Blue", "Green", "Purple"]
    move_markers = {"HIT": "red", "MISS": "dark gray", "SUNK": "black", "DEFAULT": "SystemButtonFace"}
    rows = ["+", "A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]
    row_map = {"A": 1, "B": 2, "C": 3, "D": 4, "E": 5, "F": 6, "G": 7, "H": 8, "I": 9, "J": 10}
    cardinals = ["N", "S", "W", "E"]

    def __init__(self, player_count):
        self.player_count = player_count
        self.players = {}  # key: player num, value: player object
        self.player_update = {} # key: player object, value: need update (T) or up to date (F)
        self.teams = {}  # key: team color, value: list of players (by player_num)
        self.teams_alive = {}  # key: team color, alive (T) or dead (F)
        self.team_turn = None  # Keeps track of whose turn it is
        self.first_team_turn = None  # Keeps track of which team took the first turn
        self.turn_count = 1  # Current turn count
        self.team_winner = None
        # Game Phases
        self.player_join_count = 0  # Keep track of players ready to transition to setup phase
        self.player_ready_count = 0  # Keep track of players ready to transition to game phase
        self.player_end_count = 0  # Keep track of players ready to transition to end phase
        self.game_setup = False
        self.game_start = False
        self.game_end = False

        self.player_nums = 0

    def assign_player_num(self):
        self.player_nums += 1
        return self.player_nums

    def add_player(self, player, player_num):
        self.players[player_num] = player
        self.player_update[player] = False

    def get_player(self, player_num):
        return self.players[player_num]

    def add_team(self, team, player_num):
        if team not in self.teams:
            self.teams[team] = []
            self.teams_alive[team] = True

        team_list = self.teams[team]
        team_list.append(player_num)

    def enough_teams(self):
        if len(list(self.teams.keys())) > 1:
            return True
        else:
            return False

    def select_first_team(self):
        # Randomly select a team to be first
        team_list = list(self.teams.keys())
        self.team_turn = team_list[random.randrange(len(team_list))]
        self.first_team_turn = self.team_turn

    def get_current_team_turn(self):
        return self.team_turn

    def make_move(self, attacker, defender, row, col):
        msg = defender.set_move(row, col)
        # Update state buffers for every player
        self.add_to_state_buffer(msg + ' ' + attacker.username + ' ' + defender.username + ' ' +
                                 str(row) + ' ' + str(col))
        self.game_update(attacker, defender)  # Update the game state

    def game_update(self, attacker, defender):
        # Update ship state for updating player, update state buffer for every player
        sunk_msg = defender.update_ship_state(attacker)
        sunk_tokens = sunk_msg.split()
        if sunk_tokens[0] == "SUNK":
            self.add_to_state_buffer(sunk_msg)

            # Check if defending player in team with updating player is still alive
            if defender.check_if_dead():
                self.add_to_state_buffer("ELIM_PLAYER " + attacker.username + ' ' + defender.username)
                # Check if team has been eliminated as well
                if self.teams_alive[defender.team]:
                    team_alive = False
                    player_list = self.teams[defender.team]
                    for player_num in player_list:
                        if self.players[player_num].is_alive:
                            team_alive = True
                            break
                    if not team_alive:
                        self.teams_alive[defender.team] = False
                        self.add_to_state_buffer("ELIM_TEAM " + attacker.team + ' ' + defender.team)

                        # Check if game is over
                        self.is_game_over()

        attacker.taken_turn = True  # Set attacker turn as taken
        # If game is not over from move, check if team's turn is over
        if not self.game_end:
            self.check_team_taken_turn()

    def is_game_over(self):
        alive_count = 0
        winning_team = None
        for team in self.teams_alive:
            if self.teams_alive[team]:
                alive_count += 1
                winning_team = team
        if alive_count == 1: # Game has ended
            # Set the team winner
            self.team_winner = winning_team
            self.add_to_state_buffer("GAME_END " + winning_team)
            self.game_end = True

    def check_team_taken_turn(self):
        # Find current team's turn
        index = self.get_current_team_turn()
        turn_taken = True
        for player_num in self.teams[index]:  # Determine if each player has taken their turn
            if not self.players[player_num].taken_turn:
                turn_taken = False
                break
        if turn_taken:
            # Reset current team's turn taken flag, then change turn
            for player_num in self.teams[index]:
                self.players[player_num].taken_turn = False
            self.change_team_turn()

    def change_team_turn(self):
        # Find current team's turn
        team_list = list(self.teams.keys())
        index = team_list.index(self.get_current_team_turn())
        while True: # Find next team that is alive
            index = (index + 1) % len(team_list)
            next_team = team_list[index]
            if self.teams_alive[next_team]:  # Found next team's turn
                self.team_turn = team_list[index]
                if next_team == self.first_team_turn:  # All teams took their turn, increment turn counter
                    self.turn_count += 1
                # Add team change to state buffers
                self.add_to_state_buffer("TURN_CHANGE " + str(self.turn_count) + ' ' + next_team)
                break

    def add_to_state_buffer(self, msg):
        for player_num in self.players:
            player = self.players[player_num]
            player.add_state(msg)