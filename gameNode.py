import random
import copy
import hashlib
from queues import PriorityQueue
from queues import Queue
import cPickle


class GameNode:
    ACTIONS = {
        -1: 'DoNothing',
        1: 'MoveUp',
        2: 'MoveLeft',
        3: 'MoveRight',
        4: 'MoveDown',
        5: 'PlaceBomb',
        6: 'TriggerBomb',
    }

    moves = dict([[v,k] for k,v in ACTIONS.items()])

    # General
    entitiesToDestroy = []
    killedPlayers = []
    moveThatLedHere = None
    numNeighbors = None
    myNeighbors = None
    myPlayerKey = None
    stateKey = None
    parentKey = None

    ## CoW
    changedBlocks = {}

    ## Indexes
    bombIndex = None
    explodedIndex = None
    powerUpIndex = None

    # Heuristic helper generated with index
    guessedTarget = None

    def __init__(self, gameState):
        self.state = gameState
        if 'Score' not in self.state:
            # Must be the first run....
            #print "Did not find score, initialising"
            self.generateFirstIndex()
            self.state['Score'] = 0
        self.entitiesToDestroy = []

    def setVisitedBlocks(self, visitedBlocks):
        self.state['VisitedBlocks'] = visitedBlocks

    def setMyPlayerKey(self, playerKey):
        self.myPlayerKey = playerKey

    def fastCopy(self, objectToCopy):
        return cPickle.loads(cPickle.dumps(objectToCopy, -1))

    def getScore(self):
        return self.state['Score']


    def guessTarget(self):
        guess = None

        if self.powerUpIndex:
            for p in self.powerUpIndex:
                pPosition = (p['Location']['X'] - 1, p['Location']['Y'] - 1)
                if p['$type'] == "Domain.Entities.PowerUps.SuperPowerUp, Domain":
                    guess = pPosition
                    #print p
                    break
                else:
                    if self.mDistance(self.getPosition(self.myPlayerKey), pPosition) < 23:
                        #print self.mDistance(self.getPosition(self.myPlayerKey), pPosition)
                        #print p
                        guess = pPosition

            for p in self.powerUpIndex:

                pPosition = (p['Location']['X'] - 1, p['Location']['Y'] - 1)
                if self.mDistance(self.getPosition(self.myPlayerKey), pPosition) < 8:
                    #print self.mDistance(self.getPosition(self.myPlayerKey), pPosition)
                    #print p
                    guess = pPosition


        if guess == None:
            guess = self.getMyPosition(self.myPlayerKey)

        self.guessedTarget = guess

    def cleverScoreHeuristic(self, targetScore):
        h = targetScore - self.getScore()
        bombs = self.getPlayerBombs(self.myPlayerKey)
        dZone = self.getDangerousBlocks()
        numBombs = len(bombs)
        myPos = self.getPosition(self.myPlayerKey)

        # bombs
        bFactor = 0

        for b in bombs:
            bPosition = (b['Location']['X'] - 1, b['Location']['Y'] - 1)
            #print bPosition
            bNList = self.getPossibleNeighbors(bPosition)
            #print len(bNList)
            if len(bNList) > 3:
                bFactor += len(bNList) * 0.07


        # danger
        dFactor = 0
        if myPos in dZone:
            #print "in dzone"
            dFactor = -1

        pFactor = 0

        # player danger
        playerDangerZone = self.getPlayerAvoidanceBlocks(self.myPlayerKey, 6)
        if myPos in playerDangerZone:
            #print playerDangerZone
            #print "In playerDangerZone"
            pFactor = -0.3

        # guessedTarget
        tFactor = 0
        myPosition = self.getPosition(self.myPlayerKey)
        distanceToGuessedTarget = self.mDistance(myPosition, self.guessedTarget)
        tFactor = distanceToGuessedTarget * -0.3

        #print h - bFactor - dFactor - pFactor - tFactor
        return h - bFactor - dFactor - pFactor - tFactor

    def generateFirstIndex(self):
        bombs = []
        exploded = []
        powerUps = []
        for x in xrange(0, self.state['MapWidth']):
            for y in xrange(0, self.state['MapHeight']):
                block = self.getBlock((x,y))
                if block['Bomb']:
                    bombs.append((x,y))
                if block['Exploding']:
                    exploded.append((x,y))
                if block['PowerUp']:
                    powerUps.append(block['PowerUp'])
        self.explodedIndex = exploded
        self.bombIndex = bombs
        self.powerUpIndex = powerUps

    def copySelf(self):
        newState = {}
        newState['MapSeed'] = copy.copy(self.state['MapSeed'])
        newState['CurrentRound'] = copy.copy(self.state['CurrentRound'])
        newState['Score'] = self.fastCopy(self.state['Score'])
        newState['VisitedBlocks'] = copy.copy(self.state['VisitedBlocks'])
        newState['MapHeight'] = copy.copy(self.state['MapHeight'])
        newState['MapWidth'] = copy.copy(self.state['MapWidth'])
        newState['RegisteredPlayerEntities'] = []
        for r in self.state['RegisteredPlayerEntities']:
            newState['RegisteredPlayerEntities'].append(self.fastCopy(r))
        newState['GameBlocks'] = self.state['GameBlocks']
        newSelf = GameNode(newState)
        newSelf.setMyPlayerKey(self.myPlayerKey)
        newSelf.changedBlocks = self.changedBlocks.copy()
        newSelf.explodedIndex = copy.copy(self.explodedIndex)
        newSelf.bombIndex = copy.copy(self.bombIndex)
        newSelf.guessedTarget = self.guessedTarget
        return newSelf

    def neighbors(self, playerKey):
        if self.myNeighbors == None:
            #print "bombIndex in neighbors: ", self.bombIndex
            #print self.getStatePretty()
            moves = self.getValidMoves(playerKey)
            self.myNeighbors = []
            for m in moves:
                # my move
                commands = {}
                commands[playerKey] = m
                """
                # make some assuptions about what opponenets will do:
                for p in self.getPlayers():
                    if p['Key'] != playerKey:
                        commands[p['Key']] = "TriggerBomb"
                """
                # create new neighbor
                newState = self.copySelf()
                newState.moveThatLedHere = m
                newState.processCommands(commands)
                newState.parentKey = self.getStateKey()
                #print "NEIGHBOR::::::::::::::::" ,newState.getStatePretty()
                if newState.getPlayer(playerKey)['Killed'] == False:
                    self.myNeighbors.append(newState)
                else:
                    #print "KILLED :("
                    pass
            return self.myNeighbors
        else:
            return self.myNeighbors


    def cost(self, current, next, playerKey):
        if next.getPlayer(playerKey)['Killed'] == True: # Is this even needed?
            return 999999
        else:
            return 1

    def mDistance(self, myPosition, goalPosition):
        (x1, y1) = myPosition
        (x2, y2) = goalPosition
        return (abs(x1 - x2) + abs(y1 - y2)) * 1

    def getStateKeyWorkingOriginal(self):
        if self.stateKey == None:
            blockHashes = ""
            for x in xrange(0, self.state['MapWidth']):
                for y in xrange(0, self.state['MapHeight']):
                    blockHashes += (str(self.getBlock((x,y))))
            self.stateKey = hashlib.md5(str(blockHashes) + str(self.state['RegisteredPlayerEntities']) + str(self.state['CurrentRound'])).hexdigest()
            return self.stateKey
        else:
            return self.stateKey


    def getStateKey(self):
        if self.stateKey == None:
            blockHashes = ""
            self.stateKey = hashlib.md5(str(self.changedBlocks) + str(self.state['RegisteredPlayerEntities']) + str(self.state['CurrentRound'])).hexdigest()
            return self.stateKey
        else:
            return self.stateKey


    def getPlayerUtility(self, playerKey, startPosition):
        if self.getPlayer(playerKey)['Killed'] == True:
            return 0
        return self.manhattenDistance((0,0), self.getPosition(playerKey))

    def manhattenDistance(self, a, b):
        distance = abs(b[0]-a[0]) + abs(b[1]-a[1])
        return distance

    def getValidMoves(self, playerKey):
        validMoves = []
        playerBombs = self.getPlayerBombs(playerKey)

        #Do nothing
        validMoves.append('DoNothing')


        #Check if can trigger
        # Only if we have active bombs
        # and
        # Only if we have bombs with timer > 1, otherwise there is one already Exploding
        # todo: Check if my assumptions are right here
        canTrigger = False
        if len(playerBombs) > 0:
            lowestFound = playerBombs[0]['BombTimer']
            for b in playerBombs:
                if b['BombTimer'] < lowestFound:
                    lowestFound = b['BombTimer']
            if lowestFound > 1:
                canTrigger = True

        # check if bombs with timers
        if canTrigger:
            validMoves.append('TriggerBomb')

        #Check valid directions
        myPosition = self.getPosition(playerKey)
        validMoves = validMoves + self.getValidMovement(myPosition)


        #Check if can place bomb
        myPosition = self.getPosition(playerKey)
        #print self.isBomb(myPosition)
        if self.getPlayer(playerKey)['BombBag'] > len(playerBombs) and not self.isBomb(myPosition):
            validMoves.append('PlaceBomb')

        #Return list of moves
        return validMoves


    def processCommands(self, playerCommands):

        #Speedup :)
        explosionIndex = []
        #self.reIndex()
        #self.generateIndex()
        #bombIndex = self.getBombIndex()

        self.removeExplosionsFromMap()
        self.decreaseBombTimers()
        self.detonateBombs(explosionIndex) #Recursivly triggers bombs
        self.markEntitiesForDestruction(explosionIndex)
        self.processPlayerCommands(playerCommands)
        self.markEntitiesForDestruction(explosionIndex)
        #self.applyPowerUps()
        self.destroyMarkedEntities()
        self.state['CurrentRound'] = self.state['CurrentRound'] + 1
        self.entitiesToDestroy = []

        #if self.moveThatLedHere == "TriggerBomb":
        #    print "FINISHED PROCESSING ROUND!!!!!!!"
        #    print self.getStatePretty()



    def removeExplosionsFromMap(self):
        for e in set(self.explodedIndex):
            self.updateBlock((e[0],e[1]), 'Exploding', False)
            self.explodedIndex.remove(e)


    def decreaseBombTimers(self):
        #print "bombIndex in decrease: ", bombIndex
        #print "bombIndex in decrease: ", self.bombIndex
        for b in self.bombIndex:
            #print "DECREASING BOMB TIMER b: ", b
            #print self.bombIndex
            bomb = self.getBlock(b)['Bomb']
            newBomb = self.fastCopy(bomb)
            newBomb['BombTimer'] = newBomb['BombTimer'] - 1
            self.updateBlock(b, 'Bomb', newBomb)

    def detonateBombs(self, explosionIndex):
        for b in self.bombIndex:
            bomb = self.getBlock(b)['Bomb']
            if bomb['BombTimer'] == 0:
                self.detonateBomb(b[0], b[1], bomb, explosionIndex)

    def detonateBomb(self, x, y, bomb, explosionIndex):
        if bomb['IsExploding']:
            return None


        #bomb['IsExploding'] = True
        newBomb = self.fastCopy(bomb)
        newBomb['IsExploding'] = True

        bombLocation = (bomb['Location']['X'] - 1, bomb['Location']['Y'] - 1)
        self.updateBlock(bombLocation, 'Bomb', newBomb)
        ####### BUGGGG

        #print "DETONATING BOMB AFTER SET EXPLODING: ", bomb
        ownerKey = bomb['Owner']['Key']
        player = self.getPlayer(ownerKey)
        player['BombBag'] += 1
        self.markGameBlockExploded(x, y, bomb, explosionIndex)
        bombRadius = bomb['BombRadius']

        # right
        for i in range(x + 1, x + 1 + bombRadius):
            if i > self.state['MapWidth']:
                break
            if not self.markGameBlockExploded(i, y, bomb, explosionIndex):
                break
        # Left
        for i in reversed(range(x - bombRadius, x)):
            if i < 1:
                break
            if not self.markGameBlockExploded(i, y, bomb, explosionIndex):
                break
        # Down
        for i in range(y + 1, y + 1 + bombRadius):
            if i > self.state['MapHeight']:
                break
            if not self.markGameBlockExploded(x, i, bomb, explosionIndex):
                break
        # Up
        for i in reversed(range(y - bombRadius, y)):
            if i < 1:
                break
            if not self.markGameBlockExploded(x, i, bomb, explosionIndex):
                break

    #return false if damage must not continue
    def markGameBlockExploded(self, x, y, bomb, explosionIndex):
        #print "marking exploded"
        block = self.getBlock((x,y))

        if block['Bomb']:
            self.updateBlock((x,y), 'Exploding', True)
            explosionIndex.append((x,y))
            self.explodedIndex.append((x,y))   #indexing

        if not block['Entity']:
            self.updateBlock((x,y), 'Exploding', True)
            explosionIndex.append((x,y))
            self.explodedIndex.append((x,y))   #indexing

        bombLocation = (bomb['Location']['X'] - 1, bomb['Location']['Y'] - 1)
        if block['Bomb'] and (x,y) != bombLocation:##and block['Bomb'] != bomb:
            #print "bombLocation = ", bombLocation
            #print "xy = ", (x,y)
            #print "BOMB DETONATION CHAIN REACTION SOURCE    : ", bomb['Location']
            #print "BOMB DETONATION CHAIN REACTION TRIGGERED : ", block['Bomb']['Location']
            self.detonateBomb(x, y, block['Bomb'], explosionIndex)
            self.explodedIndex.append((x,y))   #indexing
            return False

        if block['Entity']:
            if block['Entity']['$type'] == "Domain.Entities.DestructibleWallEntity, Domain":
                self.updateBlock((x,y), 'Exploding', True)
                explosionIndex.append((x,y))
                self.explodedIndex.append((x,y))   #indexing
                #process score
                if bomb['Owner']['Key'] == self.myPlayerKey:
                    self.state['Score'] += 10

                return False
            if block['Entity']['$type'] == "Domain.Entities.PlayerEntity, Domain":
                self.updateBlock((x,y), 'Exploding', True)
                explosionIndex.append((x,y))
                self.explodedIndex.append((x,y))   #indexing
                #process score
                if bomb['Owner']['Key'] == self.myPlayerKey:
                    self.state['Score'] += 50
                return True
            if block['Entity']['$type'] == "Domain.Entities.IndestructibleWallEntity, Domain":
                return False

        return True


    def markEntitiesForDestruction(self, explosionIndex):
        #if self.moveThatLedHere == "TriggerBomb":
        #    print "explosionIndex: ", explosionIndex
        for c in explosionIndex:
            block = self.getBlock(c)
            if block['Entity'] and block['Entity']['$type'] == "Domain.Entities.DestructibleWallEntity, Domain":
                self.entitiesToDestroy.append(c)
            if block['Entity'] and block['Entity']['$type'] == "Domain.Entities.PlayerEntity, Domain":
                #if self.moveThatLedHere == "TriggerBomb":
                #    print "REMOVING PLAYER"
                self.entitiesToDestroy.append(block['Entity'])
            if block['Bomb']:
                self.entitiesToDestroy.append(c)


    def processPlayerCommands(self, playerCommands):
        playerKeys = playerCommands.keys()
        random.shuffle(playerKeys)

        for playerKey in playerKeys:
            command = playerCommands[playerKey]
            x,y = self.getPosition(playerKey)
            myBlock = self.getBlock((x,y))
            player = self.getPlayer(playerKey)

            #Execute commands
            if command == "MoveRight":
                nx = x + 1
                if self.getBlock((nx,y))['Entity'] == None:
                    self.state['Score'] += 0.2
                    self.updateBlock((nx,y), 'Entity', myBlock['Entity'])
                    self.updateBlock((x,y), 'Entity', None)
                    player['Location']['X'] = player['Location']['X'] + 1
                    bombs = self.getBombs()
                    for b in bombs:
                        if b['Owner']['Key'] == playerKey:
                            newOwner = self.fastCopy(self.getPlayer(playerKey))
                            b['Owner'] = newOwner
                    if playerKey == self.myPlayerKey:
                        if (nx, y) not in self.state['VisitedBlocks']:
                            self.state['VisitedBlocks'].append((nx, y))
                            self.state['Score'] += 0.5
                        if self.isPowerUp((nx, y)):
                            self.state['Score'] += 4


            elif command == "MoveLeft":
                nx = x - 1
                if self.getBlock((nx,y))['Entity'] == None:
                    self.state['Score'] += 0.2
                    self.updateBlock((nx,y), 'Entity', myBlock['Entity'])
                    self.updateBlock((x,y), 'Entity', None)
                    player['Location']['X'] = player['Location']['X'] - 1
                    bombs = self.getBombs()
                    for b in bombs:
                        if b['Owner']['Key'] == playerKey:
                            newOwner = self.fastCopy(self.getPlayer(playerKey))
                            b['Owner'] = newOwner
                    if playerKey == self.myPlayerKey:
                        if (nx, y) not in self.state['VisitedBlocks']:
                            self.state['VisitedBlocks'].append((nx, y))
                            self.state['Score'] += 0.5
                        if self.isPowerUp((nx, y)):
                            self.state['Score'] += 4


            elif command == "MoveDown":
                ny = y + 1
                if self.getBlock((x,ny))['Entity'] == None:
                    self.state['Score'] += 0.2
                    self.updateBlock((x,ny), 'Entity', myBlock['Entity'])
                    self.updateBlock((x,y), 'Entity', None)
                    player['Location']['Y'] = player['Location']['Y'] + 1
                    bombs = self.getBombs()
                    for b in bombs:
                        if b['Owner']['Key'] == playerKey:
                            newOwner = self.fastCopy(self.getPlayer(playerKey))
                            b['Owner'] = newOwner
                    if playerKey == self.myPlayerKey:
                        if (x, ny) not in self.state['VisitedBlocks']:
                            self.state['VisitedBlocks'].append((x, ny))
                            self.state['Score'] += 0.5
                        if self.isPowerUp((x, ny)):
                            self.state['Score'] += 4

            elif command == "MoveUp":
                ny = y - 1
                if self.getBlock((x,ny))['Entity'] == None:
                    self.state['Score'] += 0.2
                    self.updateBlock((x,ny), 'Entity', myBlock['Entity'])
                    self.updateBlock((x,y), 'Entity', None)
                    player['Location']['Y'] = player['Location']['Y'] - 1

                    bombs = self.getBombs()
                    for b in bombs:
                        if b['Owner']['Key'] == playerKey:
                            newOwner = self.fastCopy(self.getPlayer(playerKey))
                            b['Owner'] = newOwner
                    if playerKey == self.myPlayerKey:
                        if (x, ny) not in self.state['VisitedBlocks']:
                            self.state['VisitedBlocks'].append((x, ny))
                            self.state['Score'] += 0.5
                        if self.isPowerUp((x, ny)):
                            self.state['Score'] += 4

            elif command == "TriggerBomb":
                playerBombs = self.getPlayerBombs(playerKey)
                if len(playerBombs) > 0:
                    lowestFound = playerBombs[0]['BombTimer']
                    triggerTarget = playerBombs[0]
                    for b in playerBombs:
                        if b['BombTimer'] < lowestFound:
                            lowestFound = b['BombTimer']
                            triggerTarget = b
                    if lowestFound > 1:
                        newBomb = triggerTarget.copy()
                        bX = newBomb['Location']['X'] - 1
                        bY = newBomb['Location']['Y'] - 1
                        newBomb['BombTimer'] = 1
                        self.updateBlock((bX,bY), 'Bomb', newBomb)


            elif command == "PlaceBomb":
                playerBombs = self.getPlayerBombs(playerKey)
                myPosition = self.getPosition(playerKey)
                if self.getPlayer(playerKey)['BombBag'] > len(playerBombs) and myBlock['Bomb'] == None:
                    self.state['Score'] += 0.7
                    newBomb = {
                     'BombRadius': player['BombRadius'],
                     'BombTimer': min(((player['BombBag'] * 3) + 1), 9),
                     'IsExploding': False,
                     'Location': player['Location'],
                     'Owner': player}
                    self.updateBlock ((x,y), 'Bomb', newBomb)
                    self.bombIndex.append((x,y))
                    #print "Updating bomb index: ", self.bombIndex
                    player['BombBag'] = player['BombBag'] - 1
            elif command == "DoNothing":
                pass
            else:
                pass

    def applyPowerUps(self):
        for x in xrange(0, self.state['MapWidth']):
            for y in xrange(0, self.state['MapHeight']):
                position = (x,y)
                block = self.getBlock(position)
                if block['PowerUp'] and block['Entity'] and block['Entity']['$type'] == "Domain.Entities.PlayerEntity, Domain":
                    player = self.getPlayer(block['Entity']['Key'])
                    if block['PowerUp']['$type'] == "Domain.Entities.PowerUps.BombRaduisPowerUpEntity, Domain":
                        player['BombRadius'] *= 2
                        self.updateBlock(position, 'PowerUp', None)
                    elif block['PowerUp']['$type'] == "Domain.Entities.PowerUps.BombBagPowerUpEntity, Domain":
                        player['BombBag'] += 1
                        self.updateBlock(position, 'PowerUp', None)
                    elif block['PowerUp']['$type'] == "Domain.Entities.PowerUps.SuperPowerUp, Domain":
                        player['BombRadius'] *= 2
                        player['BombBag'] += 1
                        player['Points'] += 50
                        self.updateBlock(position, 'PowerUp', None)

    def destroyMarkedEntities(self):
        for e in self.entitiesToDestroy:
            if type(e) == dict:
                playerKey = e['Key']
                player = self.getPlayer(playerKey)
                self.killedPlayers.append(player)
                player['Killed'] = True
            else:
                block = self.getBlock((e))
                if block['Entity'] and block['Entity']['$type'] == "Domain.Entities.DestructibleWallEntity, Domain":
                    self.updateBlock(e, 'Entity', None)

                if block['Bomb']:
                    self.updateBlock(e, 'Bomb', None)
                    #todo
                    #print "Removing from bombIndex: ", e
                    self.bombIndex.remove(e)


    def testIfInOpponentDanger(self, position):
        bombDangerZone = []
        #print "testing position: ", position
        for b in self.getBombs():
            #print b
            if b['Owner']['Key'] != self.myPlayerKey:
                bombDangerZone += self.simulateBombTrigger(b)
        if position in bombDangerZone:
            return True
        else:
            return False

    def simulateBombTrigger(self, bomb):
        explosionIndex = []
        self.triggerBomb(bomb, explosionIndex)
        return explosionIndex

    def triggerBomb(self, bomb, explosionIndex):
        x = bomb['Location']['X'] - 1
        y = bomb['Location']['Y'] - 1
        bombRadius = bomb['BombRadius']

        # right
        for i in range(x + 1, x + 1 + bombRadius):
            if i > self.state['MapWidth']:
                break
            if not self.simulateExplode(i, y, bomb, explosionIndex):
                break

        # Left
        for i in reversed(range(x - bombRadius, x)):
            if i < 1:
                break
            if not self.simulateExplode(i, y, bomb, explosionIndex):
                break
        # Down
        for i in range(y + 1, y + 1 + bombRadius):
            if i > self.state['MapHeight']:
                break
            if not self.simulateExplode(x, i, bomb, explosionIndex):
                break
        # Up
        for i in reversed(range(y - bombRadius, y)):
            if i < 1:
                break
            if not self.simulateExplode(x, i, bomb, explosionIndex):
                break



    #return false if damage must not continue
    def simulateExplode(self, x, y, bomb, explosionIndex):
        if (x,y) in explosionIndex:
            return None
        #print "marking exploded"
        block = self.getBlock((x,y))

        if block['Bomb']:
            explosionIndex.append((x,y))

        if not block['Entity']:
            explosionIndex.append((x,y))
        bombLocation = (bomb['Location']['X'] - 1, bomb['Location']['Y'] - 1)

        if block['Bomb'] and (x,y) != bombLocation:
            self.triggerBomb(block['Bomb'], explosionIndex)
            return False

        if block['Entity']:
            if block['Entity']['$type'] == "Domain.Entities.DestructibleWallEntity, Domain":
                explosionIndex.append((x,y))
                return False
            if block['Entity']['$type'] == "Domain.Entities.PlayerEntity, Domain":
                explosionIndex.append((x,y))
                return True
            if block['Entity']['$type'] == "Domain.Entities.IndestructibleWallEntity, Domain":
                return False

        return True


    def getStatePretty(self):
        prettyMap = ""
        prettyMap += "ROUND                 : " + str(self.state['CurrentRound'])
        prettyMap += "\n"
        prettyMap += "My Key                : " + str(self.getStateKey())
        prettyMap += "\n"
        prettyMap += "Parent Key            : " + str(self.parentKey)
        prettyMap += "\n"
        prettyMap += "My Player Key         : " + str(self.myPlayerKey)
        prettyMap += "\n"
        prettyMap += "Score                 : " + str(self.state['Score'])
        prettyMap += "\n"
        prettyMap += "self.moveThatLedHere  : " + str(self.moveThatLedHere)
        prettyMap += "\n"

        for y in range(0, self.state['MapWidth']):
            row = ""
            for x in range(0, self.state['MapHeight']):
                block = self.getBlock((x,y))
                if block['Exploding']:
                    row = row + "*"
                elif block['PowerUp'] and block['PowerUp']['$type'] == "Domain.Entities.PowerUps.BombRaduisPowerUpEntity, Domain":
                    row = row + "!"
                elif block['PowerUp'] and block['PowerUp']['$type'] == "Domain.Entities.PowerUps.BombBagPowerUpEntity, Domain":
                    row = row + "&"
                elif block['PowerUp'] and block['PowerUp']['$type'] == "Domain.Entities.PowerUps.SuperPowerUp, Domain":
                    row = row + "$"
                elif block['Entity'] and block['Entity']['$type'] == "Domain.Entities.DestructibleWallEntity, Domain":
                    row = row + "+"
                elif block['Entity'] and block['Entity']['$type'] == "Domain.Entities.IndestructibleWallEntity, Domain":
                    row = row + "#"
                elif block['Entity'] and block['Entity']['$type'] == "Domain.Entities.PlayerEntity, Domain":
                    if block['Bomb']:
                        row = row + block['Entity']['Key'].lower()
                    else:
                        row = row + block['Entity']['Key']
                elif block['Bomb']:
                    timer = block['Bomb']['BombTimer']
                    row = row + str(timer)
                elif (x,y) in self.state['VisitedBlocks']:
                    row = row + "."
                else:
                    row = row + " "
            prettyMap = prettyMap + row + "\n"
        prettyMap += "Players:\n"
        for p in self.state['RegisteredPlayerEntities']:
            prettyMap += str(p)
            prettyMap += "\n"
        return prettyMap;

    def getPosition(self, playerKey):
        for p in self.state['RegisteredPlayerEntities']:
            if p['Key'] == playerKey:
                return (p['Location']['X'] - 1 , p['Location']['Y'] - 1)

    def getPlayer(self, playerKey):
        for p in self.state['RegisteredPlayerEntities']:
            if p['Key'] == playerKey:
                return p

    def getPlayers(self):
        players = []
        for p in self.state['RegisteredPlayerEntities']:
            players.append(p)
        return players

    def getAlivePlayers(self):
        players = {}
        for p in self.state['RegisteredPlayerEntities']:
            if not p['Killed']:
                players[p['Key']] = p
        return players

    def getValidMovement(self, position):
        moves = []
        if self.isEmpty((position[0] - 1, position[1])):
            moves.append('MoveLeft')
        if self.isEmpty((position[0] + 1, position[1])):
            moves.append('MoveRight')
        if self.isEmpty((position[0], position[1] - 1)):
            moves.append('MoveUp')
        if self.isEmpty((position[0], position[1] + 1)):
            moves.append('MoveDown')
        return moves


    def getPlayerBombs(self, playerKey):
        myBombs = []
        #print "bombs: ", self.getBombs()
        for b in self.getBombs():
            #print "BBBBBBBBBBBBBB: ", b
            if b['Owner']['Key'] == playerKey:
                myBombs.append(b)
        return myBombs


    def getBombs(self):
        #print "GETTING BOMBS"
        bombList = []
        #print "bombIndex: ", self.getBombIndex()
        for b in self.bombIndex:
            bombList.append(self.getBlock(b)['Bomb'])
        #print "bombIndex: ", self.bombIndex
        return bombList

    def getBombsOld(self):
        bombList = []
        for x in xrange(0, self.state['MapWidth']):
            for y in xrange(0, self.state['MapHeight']):
                block = self.getBlock((x,y))
                if block['Bomb']:
                    bombList.append(block['Bomb'])
        return bombList


    def getMyPosition(self, playerKey):
        for p in self.state['RegisteredPlayerEntities']:
            if p['Key'] == playerKey:
                return (p['Location']['X'] - 1 , p['Location']['Y'] - 1)

    def getPowerups(self):
        powerups = []
        for x in xrange(0, self.state['MapWidth']):
            for y in xrange(0, self.state['MapHeight']):
                if self.getBlock((x,y))['PowerUp']:
                    powerups.append(self.getBlock((x,y)))
        return powerups;

    #todo: players are also destructable
    def isDestructable(self, position):
        block = self.getBlock(position)
        if block['Entity'] and block['Entity']['$type'] == "Domain.Entities.DestructibleWallEntity, Domain":
            return True;
        elif block['Entity'] and block['Entity']['$type'] == "Domain.Entities.PlayerEntity, Domain":
            return True;

    def isDestructableWall(self, position):
        block = self.getBlock(position)
        if block['Entity'] and block['Entity']['$type'] == "Domain.Entities.DestructibleWallEntity, Domain":
            return True;


    def isPowerUp(self, position):
        if self.getBlock(position)['PowerUp']:
            return True
        else:
            return False

    def getBlock(self, position):
        if position in self.changedBlocks.keys():
            return self.changedBlocks[position]
        else:
            return self.state['GameBlocks'][position[0]][position[1]]

    def updateBlock(self, position, key, newValue):
        blockToUpdate = self.getBlock(position)
        newBlock = self.fastCopy(blockToUpdate)
        newBlock[key] = newValue
        self.changedBlocks[position] = newBlock

    def isBomb(self, position):
        block = self.getBlock(position)
        if self.getBlock(position)['Bomb']:
            return True
        else:
            return False

    def isEmpty(self, position):
        block = self.getBlock(position)
        if block['Entity'] and (
            (block['Entity']['$type'] == "Domain.Entities.IndestructibleWallEntity, Domain")
            or
            (block['Entity']['$type'] == "Domain.Entities.DestructibleWallEntity, Domain")
            or
            (block['Entity']['$type'] == "Domain.Entities.PlayerEntity, Domain")
            or
            self.isBomb((block['Location']['X'] - 1, block['Location']['Y'] - 1))):
            return False
        elif block['Bomb']:
            return False
        else:
            return True

    def simplifiedCost(self, current, next):
        nextNode = self.state['GameBlocks'][next[0]][next[1]]
        if nextNode['Entity'] and nextNode['Entity']['$type'] == "Domain.Entities.DestructibleWallEntity, Domain":
            return 5;
        else:
            return 1;

    def getEmptyNeighbors(self, position):
        neighbors = []
        nList = []
        #Python supports negative indexes :)
        #print position
        neighbors.append(self.getBlock((position[0] - 1,position[1]))) #Left
        neighbors.append(self.getBlock((position[0] + 1,position[1]))) #Right
        neighbors.append(self.getBlock((position[0],position[1] - 1))) #Up
        neighbors.append(self.getBlock((position[0],position[1] + 1))) #Down
        for n in neighbors:
            #print n
            if n['Entity'] and (n['Entity']['$type'] == "Domain.Entities.IndestructibleWallEntity, Domain"
               or n['Entity']['$type'] == "Domain.Entities.DestructibleWallEntity, Domain") :
                pass
            elif n['Bomb']:
                pass
            else:
                nList.append((n['Location']['X'] - 1 , n['Location']['Y'] - 1))
        return nList

    def getPossibleNeighbors(self, position):
        neighbors = []
        nList = []
        #Python supports negative indexes :)
        #print position
        neighbors.append(self.getBlock((position[0] - 1,position[1]))) #Left
        neighbors.append(self.getBlock((position[0] + 1,position[1]))) #Right
        neighbors.append(self.getBlock((position[0],position[1] - 1))) #Up
        neighbors.append(self.getBlock((position[0],position[1] + 1))) #Down
        for n in neighbors:
            #print n
            if n['Entity'] and n['Entity']['$type'] == "Domain.Entities.IndestructibleWallEntity, Domain":
                pass
            else:
                nList.append((n['Location']['X'] - 1 , n['Location']['Y'] - 1))
        return nList

    def getDangerousBlocks(self):
        bombs = self.getBombs()
        dangerZone = []
        for b in bombs:
            dangerZone += self.getBombDangerZone(b)
        return dangerZone

    def getBombDangerZone(self, bomb):
        #print "Checking dangerZone for bomb: ", bomb
        dangerZone = []
        bombLocation = (bomb['Location']['X'] - 1, bomb['Location']['Y'] - 1)
        bombRadius = bomb['BombRadius']
        neighbors = self.getPossibleNeighbors(bombLocation)
        dangerZone.append(bombLocation)
        dangerZone = dangerZone + neighbors
        for n in neighbors:
            delta = (n[0] - bombLocation[0]), (n[1] - bombLocation[1])
            #print "getDangerZone, processing neighbor: ", n
            #print "neighbor Delta: ", delta
            count = 1
            while count < bombRadius:
                newPos = (n[0] + delta[0] * count, n[1] + delta[1] * count)
                #print "newPos: ", newPos
                if self.isEmptyExcludingPlayers(newPos):
                    dangerZone.append(newPos)
                else:
                    #print "Appending even though breaking: ", newPos
                    #dangerZone.append(newPos)
                    break
                count = count + 1
        return dangerZone

    def isEmptyExcludingPlayers(self, position):
        block = self.getBlock(position)
        if block['Entity'] and (
            (block['Entity']['$type'] == "Domain.Entities.IndestructibleWallEntity, Domain")):
            return False
        else:
            return True

    def getBombTimer(self, playerKey):
        player = self.getPlayer(playerKey)
        return min(((player['BombBag'] * 3) + 1), 9)

    def getBombRadius(self, playerKey):
        player = self.getPlayer(playerKey)
        return player['BombRadius']


    def getPlayerAvoidanceBlocks(self, playerKey, playerDangerRadius):
        """ A list of blocks I should avoid because other players are there """
        playerDangerZone = []
        players = self.getPlayers()
        for p in players:
            if p['Key'] != playerKey:
                pl = (p['Location']['X'] - 1, p['Location']['Y'] - 1)
                playerDangerZone += self.getPlayerDangerZone(pl, playerDangerRadius)
        return playerDangerZone

    def getPlayerDangerZone(self, playerLocation, playerDangerRadius):
        """ Return a list of blocks around playerLocation extending to playerDangerRadius with same algorythm as bomb explosions """
        dangerZone = []
        neighbors = self.getPossibleNeighbors(playerLocation)
        dangerZone.append(playerLocation)
        dangerZone = dangerZone + neighbors
        for n in neighbors:
            delta = (n[0] - playerLocation[0]), (n[1] - playerLocation[1])
            count = 1
            while count < playerDangerRadius:
                newPos = (n[0] + delta[0] * count, n[1] + delta[1] * count)
                if self.isEmptyExcludingPlayers(newPos):
                    dangerZone.append(newPos)
                else:
                    break
                count = count + 1
        return dangerZone
