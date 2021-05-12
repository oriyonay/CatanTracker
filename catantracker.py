#  _____       _            _____              _             
# /  __ \     | |          |_   _|            | |            
# | /  \/ __ _| |_ __ _ _ __ | |_ __ __ _  ___| | _____ _ __ 
# | |    / _` | __/ _` | '_ \| | '__/ _` |/ __| |/ / _ \ '__|
# | \__/\ (_| | || (_| | | | | | | | (_| | (__|   <  __/ |   
#  \____/\__,_|\__\__,_|_| |_\_/_|  \__,_|\___|_|\_\___|_|   
# 
# a settlers of catan board tracker, written by ori yonay

"""
NOTES:
 - THIS PROGRAM IS BUILT TO BE SIMPLE, NOT EFFICIENT! The data handled by this program is small enough that we don't need to be very efficient, so we go for simplicity :)
 - There is no support for the expansion pack, only for the classic version!
 - x and y coordinates are flipped (i.e., x is rows and y is columns) for indexing convenience

TODO:
 - in handle_build: add verification for building a city. does the user already have a settlement built there?
"""

VERSION = '0.0.5'

# a class to store information about a player:
class player:
  def __init__(self):
    self.victory_points = 0
    self.unplayed_dev_cards = 0
    self.played_dev_cards = []
    self.resources = {
      'wood' : 0,
      'brick' : 0,
      'wheat' : 0,
      'sheep' : 0,
      'ore' : 0
    }

  def print_info(self):
    print('VPs: %d' % self.victory_points)
    print('total development cards: %d' % (len(self.played_dev_cards) + self.unplayed_dev_cards))
    print('played development cards: %s' % ', '.join(sorted(self.played_dev_cards)))
    print('resources:')
    for resource, amount in self.resources.items():
      if amount == 0: continue
      print('\t%d %s' % (amount, resource))
        
# a class to store information about a tile:
# (the 'settlements' list will store a list of players that have settlements
# on this tile, and two entries for a city - for the sake of simplicity).
# 'blocked' is True when the robber is on this tile
class tile:
  def __init__(self, resource, number):
    self.resource = resource
    self.number = number
    self.blocked = False
    self.settlements = []

# a class to store the game state:
class game:
  def __init__(self, players, tiles, robber):
    self.players = players
    self.tiles = tiles
    self.robber = robber
    self.longest_road = None
    self.largest_army = None

# a 'pairwise' function for pairwise iteration of lists
# (i.e., if list x contains [1, 2, ..., 10] then pairwise iteration would be
# (1, 2), (3, 4), ..., (9, 10)
def pairwise(it):
  x = iter(it)
  return zip(x, x)
        
# a list of possible tile names:
TILE_NAMES = ['wood', 'brick', 'wheat', 'sheep', 'ore', 'desert']
RESOURCE_NAMES = TILE_NAMES[:-1]

# a list of error messages:
ERRORS = [
  'error: invalid tile configuration. please try again.',
  'error: action not recognized. type \'help\' for manual.',
  'error: unexpected error. please try again.',
  'error: robber can\'t stay in the same spot. please try again.',
  'error: robbed player does not have enough resources. please try again.',
  'error: development card not recognized. plrease try again.',
  'error: resource type not recognized. please try again.',
  'error: insufficient resources.'
]

# names of development card names:
DEV_CARDS = ['knight', 'year of plenty', 'monopoly', 'road building', 'vp', 'victory point']

# a constant that we can return when an error occurs:
FAILURE = 123456789

# if someone was to build a settlement on tile (x, y) in direction d,
# these are the offsets we would have to add to (x, y) to get the 
# adjacent tiles:
directions = {
  'N' : [(-1, -1), (-1, 0)],
  'NE' : [(-1, 0), (0, 1)],
  'SE' : [(0, 1), (1, 0)],
  'S' : [(1, 0), (1, -1)],
  'SW' : [(1, -1), (0, -1)],
  'NW' : [(0, -1), (-1, -1)]
}

FANCY_TITLE = [
  ' _____       _            _____              _             ',
  '/  __ \     | |          |_   _|            | |            ',
  '| /  \/ __ _| |_ __ _ _ __ | |_ __ __ _  ___| | _____ _ __ ',
  '| |    / _` | __/ _` | \'_ \| | \'__/ _` |/ __| |/ / _ \ \'__|',
  '| \__/\ (_| | || (_| | | | | | | | (_| | (__|   <  __/ |   ',
  ' \____/\__,_|\__\__,_|_| |_\_/_|  \__,_|\___|_|\_\___|_|   ',
  '                                                           '
]

def print_fancy_title():
  for row in FANCY_TITLE: print(row)

def print_about_menu():
  print('----- catantracker v%s -----' % VERSION)
  print('written by ori yonay')
  print('github @oriyonay :)')

def print_help_menu():
  f = open('help_menu.txt')
  for line in f.readlines():
    print(line.strip())

# coordinate_to_linear: converts catan coordinates from 'coordinate form' to 'linear form'.
# we define 'coordinate form' as a pair of (x, y) coordinates of:
# (number of tiles down, number of tiles right) in human-indexing, and convert 
# to the zero-indexed 'linear form' which counts from 0 to 19:
translation_x = [0, 0, 3, 7, 12, 16]
def coordinate_to_linear(coord):
  return translation_x[coord[0]] + coord[1] - 1

# performs the opposite conversion, from linear form to coordinate form:
def linear_to_coordinate(lin):
  for idx, c in enumerate(translation_x):
    if c > lin: break
  return (idx-1, lin - translation_x[idx-1] + 1)

# valid_coordinate: is the given coordinate valid?
# max_y_coords: a list to store the max y-coordinates for any given x (indexed by coordinate, so first entry doesn't matter)
max_y_coords = [0, 3, 4, 5, 4, 3]
def valid_coordinate(coord):
  return coord[1] in range(1, max_y_coords[coord[0]]+1)

# adjacent_tiles: returns a list of all tiles (including itself) that touch a given vertex.
def adjacent_tiles(coord, direction):
  adjacent = [coord]
  for x, y in directions[direction]:
    # make sure new coordinate is valid (i.e., not off-bounds) before adding it:
    new_x, new_y = coord[0] + x, coord[1] + y
    if valid_coordinate((new_x, new_y)):
      adjacent.append((new_x, new_y))
  return adjacent

# ---------- action handling functions ---------- #
# in these functions, g is the game object, and q is the query:
def handle_roll(g, q):
  # user could have entered the sum or the individual dice values:
  if len(q) > 2:
    print(ERRORS[1])
    return FAILURE
  
  # get the roll value:
  roll = sum(int(i) for i in q)

  if roll == 7:
    print('make sure to move the robber!')

    # which players have more than 7 resources?
    for name, player_obj in g.players.items():
      num_cards = sum(player_obj.resources.values())
      if num_cards > 7:
        print('%s has more than 7 (%d) cards!' % (name, num_cards))

  # distribute resources:
  for tile in g.tiles:
    if tile.number == roll and not tile.blocked:
      for settlement_player in tile.settlements:
        settlement_player.resources[tile.resource] += 1

def handle_build(g, q):
  # if this is a road, then we do nothing:
  if q[2] == 'road': return

  # input validation:
  if len(q) != 7:
    print(ERRORS[1])
    return FAILURE

  # parse information:
  building_player = q[0]
  coord = (int(q[4]), int(q[5]))
  direction = q[6].upper()

  # update settlement information in tiles:
  for adj_coord in adjacent_tiles(coord, direction):
    tile = g.tiles[coordinate_to_linear(adj_coord)]
    tile.settlements.append(g.players[building_player])

  # update victory point information:
  g.players[building_player].victory_points += 1

def handle_buy(g, q):
  # input validation: make sure we're 'buying' a development card:
  # (this is a very soft test that also allows for the word 'devcard'):
  if q[2].startswith('dev'):
    player_name = q[0]
    g.players[player_name].unplayed_dev_cards += 1

def handle_longest_road(g, q):
  # if the longest road was taken from another user, take away 2 VPs:
  if g.longest_road is not None:
    g.players[g.longest_road].victory_points -= 2

  # give new longest road owner 2 VPs and update 'longest road' ownership status:
  player_name = q[0]
  g.players[player_name].victory_points += 2
  g.longest_road = player_name

def handle_move(g, q):
  # input validation:
  if len(q) != 6:
    print(ERRORS[1])
    return FAILURE

  robber_coord = (int(q[4]), int(q[5]))
  robber_linear = coordinate_to_linear(robber_coord)

  # if the robber is moved to the same spot, this is illegal:
  if g.robber == robber_linear:
    print(ERRORS[3])
    return FAILURE

  # move the robber:
  g.tiles[g.robber].blocked = False
  g.tiles[robber_linear].blocked = True
  g.robber = robber_linear

def handle_play(g, q):
  # input validation:
  if len(q) < 3: return FAILURE

  # parse information:
  player_name = q[0]
  card = ' '.join(q[2:])

  if card not in DEV_CARDS:
    print(ERRORS[5])
    return FAILURE

  # update player information:
  g.players[player_name].unplayed_dev_cards -= 1
  g.players[player_name].played_dev_cards.append(card)

  if card == 'knight':
    # get new robber location:
    while True:
      print('what is the new location of the robber? (x y):')
      coord = [int(i) for i in input().split()]
      if not valid_coordinate(coord): continue

      # move the robber:
      query = ('%s moves robber to %d %d' % (player_name, coord[0], coord[1])).split()
      if handle_move(g, query) != FAILURE: break

    # check and handle largest army:
    num_knights = g.players[player_name].played_dev_cards.count('knight')
    if num_knights >= 3:
      largest_army = True
      for other_player, player_obj in g.players.items():
        if other_player != player_name:
          if player_obj.played_dev_cards.count('knight') >= num_knights:
            largest_army = False
            break
      
      if largest_army:
        if g.largest_army is not None:
          g.largest_army.victory_points -= 2
        g.largest_army = g.players[player_name]
        g.largest_army.victory_points += 2

  elif card == 'vp' or card == 'victory point':
    g.players[player_name].victory_points += 1

  elif card == 'road building': return
  elif card == 'year of plenty':
    # input validation:
    while True:
      print('which two resources did %s take? (for example, \'wheat ore\')' % player_name)
      resources = input().split()
      if len(resources) != 2: continue
      valid = True
      for r in resources:
        if r not in RESOURCE_NAMES:
          valid = False
      if valid: break
    
    # update player's cards:
    for resource in resources:
      g.players[player_name].resources[resource] += 1

  elif card == 'monopoly':
    # input validation:
    while True:
      print('which resource will %s steal?' % player_name)
      resource = input()
      if resource in RESOURCE_NAMES: break
    
    # steal resources:
    for name, player_obj in g.players.items():
      if name == player_name: continue
      g.players[player_name].resources[resource] += player_obj.resources[resource]
      player_obj.resources[resource] = 0

def handle_rob(g, q):
  # input validation:
  if len(q) < 4 or len(q) > 5: return FAILURE

  robbing_player = q[0]
  robbed_player = q[2]
  amount = 1 if len(q) == 4 else int(q[3])
  resource_type = q[-1]

  # check that the robbed player really does have this resource:
  if g.players[robbed_player].resources[resource_type] < amount:
    print(ERRORS[4])
    return FAILURE

  g.players[robbing_player].resources[resource_type] += 1
  g.players[robbed_player].resources[resource_type] -= 1

def handle_give(g, q):
  # this is an admin command, so not much input validation..
  given_player = q[1]
  for resource_num, resource_type in pairwise(q[2:]):
    g.players[given_player].resources[resource_type] += int(resource_num)


def handle_take(g, q):
  # this is an admin command, so not much input validation..
  taken_player = q[1]
  for resource_num, resource_type in pairwise(q[2:]):
    g.players[taken_player].resources[resource_type] -= int(resource_num)

def handle_trade(g, q):
  player_one = q[0]

  # if the trade is with the bank (4 for 1 or something similar):
  if q[2] != 'with':
    trade_str = ' '.join(q[2:])
    trade_give, trade_get = [i.split() for i in trade_str.split('for')]

    # make sure all resources do exist:
    for _, resource_type in pairwise(trade_give + trade_get):
      if resource_type not in RESOURCE_NAMES:
        print(ERRORS[6])
        return FAILURE

    # make sure trading player has sufficient resources:
    for resource_num, resource_type in pairwise(trade_give):
      if g.players[player_one].resources[resource_type] < int(resource_num):
        print(ERRORS[7])
        return FAILURE

    for resource_num, resource_type in pairwise(trade_give):
      g.players[player_one].resources[resource_type] -= int(resource_num)
    
    for resource_num, resource_type in pairwise(trade_get):
      g.players[player_one].resources[resource_type] += int(resource_num)

    return

  # if the trade is between two people:
  player_two = q[3]
  trade_str = ' '.join(q[4:])
  trade_give, trade_get = [i.split() for i in trade_str.split('for')]

  # make sure all resources do exist:
  for _, resource_type in pairwise(trade_give + trade_get):
    if resource_type not in RESOURCE_NAMES:
      print(resource_type)
      print(ERRORS[6])
      return FAILURE

  # make sure each player has all cards:
  for resource_num, resource_type in pairwise(trade_give):
    if g.players[player_one].resources[resource_type] < int(resource_num):
      print(ERRORS[7])
      return FAILURE

  for resource_num, resource_type in pairwise(trade_get):
    if g.players[player_two].resources[resource_type] < int(resource_num):
      print(ERRORS[7])
      return FAILURE

  # perform the trade:
  for resource_num, resource_type in pairwise(trade_give):
    g.players[player_one].resources[resource_type] -= int(resource_num)
    g.players[player_two].resources[resource_type] += int(resource_num)
  
  for resource_num, resource_type in pairwise(trade_get):
    g.players[player_one].resources[resource_type] += int(resource_num)
    g.players[player_two].resources[resource_type] -= int(resource_num)

def handle_resources(g):
  for name, player_obj in g.players.items():
    print('PLAYER: %s' % name)
    player_obj.print_info()
    print()

def handle_total(g, q):
  # input validation:
  if len(q) != 2: return FAILURE

  resource = q[1]
  total = 0
  for p in g.players.values():
    total += p.resources[resource]
  print('all players hold a total of %d %s' % (total, resource))

if __name__ == '__main__':
  # ---------- main program logic ---------- #
  print_fancy_title()
  print('welcome to catantracker!')
    
  while True:
    print('how many players will be playing?')
    num_players = int(input())
    if num_players in range(2, 5): break
    
  players = {}
  number_words = ['first', 'second', 'third', 'fourth']
  for i in range(num_players):
    while True:
      print('what\'s the %s player\'s name?' % number_words[i])
      name = input()
            
      # make sure that the name doesn't appear twice:
      if name in players: continue
      players[name] = player()
      break
        
  print('great!\nwhat does the board look like?')
  print('starting from the top left, what are the tiles and their numbers?')
  print('(for example, if a tile is ore and is on a 5, please type \'ore 5\'):')
  tiles = []
  desert_location = 0
    
  for i in range(19):
    while True:
      tile_info = input()
      if tile_info.lower() == 'desert':
        tiles.append(tile('desert', None))
        desert_location = i
        break
            
      try:
        resource, number = tile_info.split()
        number = int(number)
        if resource not in TILE_NAMES or number not in range(1, 13): 
          print(ERRORS[0])
          continue
            
        tiles.append(tile(resource, number))
        break
      except:
        print(ERRORS[0])

  # now we can construct the game object:
  g = game(players, tiles, desert_location)

  # storing the last exception (to print if user asks):
  last_exception = 'there have been no exceptions so far.'
            
  print('great! let\'s start the game!')
  print('enter an action, or \'help\' for the help menu')
  while True:
    try:
      # is there a winner?
      for player_name, player_obj in g.players.items():
        if player_obj.victory_points >= 10:
          print('%s WINS! GAME OVER!' % player_name.upper())
          exit()

      # tokenize input:
      action = input().lower().split()

      # if the user entered nothing, ignore it:
      if len(action) == 0: continue

      # if the user entered a 'comment', ignore it:
      if action[0].strip().startswith('#'): continue

      # what type of action is this?
      # we try to match all actions in order of expected length to avoid checking 
      # for len(action) all the time - so we don't have to do something like
      # 'if len(action) > 1 and ...', for example

      # try to match actions of size >= 1:
      if action[0] == 'gameover': 
        break
      elif action[0] == 'about':
        print_about_menu()
      elif action[0] == 'help' or action[0] == 'manual':
        print_help_menu()
      elif action[0] == 'roll':
        handle_roll(g, action[1:])
      elif action[0] == 'total':
        handle_total(g, action)
      elif action[0] == 'cmd':
        print('>> ', end='')
        exec(input())
      elif action[0] == 'give':
        handle_give(g, action)
      elif action[0] == 'take':
        handle_take(g, action)
      elif action[0] == 'resources' or action[0] == 'info':
        handle_resources(g)
      elif action[0].startswith('error'):
        print(last_exception)
      
      # if the action is of size 1, then nothing was found:
      elif len(action) == 1:
        print(ERRORS[1])
        continue

      # try to match actions of size > 1:
      elif action[1].startswith('build'):
        handle_build(g, action)
      elif action[1].startswith('buy'):
        handle_buy(g, action)
      elif 'longest road' in ' '.join(action):
        handle_longest_road(g, action)
      elif action[1].startswith('move'):
        handle_move(g, action)
      elif action[1].startswith('play'):
        handle_play(g, action)
      elif action[1].startswith('rob'):
        handle_rob(g, action)
      elif action[1].startswith('trade'):
        handle_trade(g, action)
      else:
        print(ERRORS[1])

    except Exception as e:
      last_exception = e
      print(ERRORS[2])
      continue

  print('game over!')