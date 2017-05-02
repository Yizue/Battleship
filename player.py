# Player - object represents an individual player
from game import Game

class Player():
    c_state = {"Empty": '-', "Ship": 'S', "Hit": 'H', "Miss": 'M',  "Sunk": 'X'}

    def __init__(self, username, team, player_num):
        self.username = username
        self.team = team
        self.player_num = player_num
        self.is_alive = True  # Player alive or eliminated
        self.taken_turn = False  # If this player has taken their turn yet
        # 10x10 board for this player
        self.grid = [[Player.c_state["Empty"] for i in range(11)] for j in range(11)]
        # First row and column store coordinate axis values
        self.grid[0][0] = '+'
        for row in range(1, 11):
            self.grid[row][0] = Game.rows[row]
        for col in range(1, 11):
            self.grid[0][col] = col
        self.ship_coords = {"carrier": [], "battleship": [], "cruiser": [], "submarine": [], "destroyer": []}
        # Ship state - True (Afloat), False (Sunk)
        self.ship_state = {"carrier": True, "battleship": True, "cruiser": True, "submarine": True, "destroyer": True}
        # Stores every message player needs to receive
        self.chat_buffer = []
        # Stores every state change notification player needs to receive
        self.state_buffer = []

    def get_grid_coordinate(self, row, col):
        return self.grid[row][col]

    def set_grid_coordinate(self, row, col, cell_state):
        self.grid[row][col] = cell_state

    def get_grid(self):
            return '\n'.join(' '.join(str(cell) for cell in row) for row in self.grid)

    def get_ship_coordinates(self):
        return self.ship_coords

    def set_ship_coordinates(self, ship, coords):
        self.ship_coords[ship] = coords

    def set_move(self, row, col):
        cell = self.get_grid_coordinate(row, col)
        if cell == Player.c_state["Ship"]:  # Hit the ship
            self.set_grid_coordinate(row, col, Player.c_state["Hit"])
            return "HIT"
        else:  # Miss the ship
            self.set_grid_coordinate(row, col, Player.c_state["Miss"])
            return "MISS"

    # Updates the current state of each ship
    def update_ship_state(self, attacker):
        for ship in self.ship_coords:
            # Check through every afloat ship
            if self.ship_state[ship]:
                is_sunk = True
                for coord in self.ship_coords[ship]:
                    coordinates = coord.split('_')
                    cell = self.get_grid_coordinate(int(coordinates[0]), int(coordinates[1]))
                    if cell != Player.c_state["Hit"]:
                        is_sunk = False
                        break
                if is_sunk:
                    for coord in self.ship_coords[ship]:
                        coordinates = coord.split('_')
                        self.set_grid_coordinate(int(coordinates[0]), int(coordinates[1]), Player.c_state["Sunk"])
                    self.ship_state[ship] = False
                    return "SUNK " + attacker.username + ' ' + self.username + ' ' + ship + ' ' + \
                           ' '.join(self.ship_coords[ship])
        return "NO_CHANGE"

    # Returns True if player has no more ships or False otherwise
    def check_if_dead(self):
        for ship in self.ship_state:
            if self.ship_state[ship]:
                return False  # Afloat ship found
        # All ships sunk
        self.is_alive = False
        return True

    def add_chat_message(self, msg):
        self.chat_buffer.append(msg)

    def get_chat_messages(self):
        return self.chat_buffer

    def clear_chat_messages(self):
        self.chat_buffer = []

    def add_state(self, msg):
        self.state_buffer.append(msg)

    def get_state_buffer(self):
        return self.state_buffer

    def clear_state_buffer(self):
        self.state_buffer = []