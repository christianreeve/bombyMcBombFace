#
import time

startTime = time.time()
timedSearchTimeout = time.time() + 1.6


import argparse
import json
import logging
import os
import cPickle
from gameNode import GameNode
from queues import PriorityQueue
from time import sleep


logger = logging.getLogger()
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)-7s - [%(funcName)s] %(message)s')
# uncomment for submission
logger.disabled = True

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
expandedNodes = {}

def main(player_key, output_path):
    ############################################################  load state
    with open(os.path.join(output_path, 'state.json'), 'r') as f:
        originalState = f.read().decode('utf-8-sig')

    ### LOAD STATE
    playerKey = player_key
    action = None
    firstGameNode = GameNode(json.loads(originalState))

    #logger.info("FIRST NODE: " + firstGameNode.getStatePretty())
    startPosition = firstGameNode.getMyPosition(playerKey)
    visitedBlocks = []

    ############################################################  visited blocks
    # load visited blocks is round isnt 0
    ###### TODO - fix this bug
    #
    if firstGameNode.state['CurrentRound'] == 1:
        #logger.info("Round ZERO, initialising visitedBlocks...")
        visitedBlocks.append(startPosition)
        with open("visited.blocks.pickle", "wb") as f:
            cPickle.dump(visitedBlocks, f)
    else:
        # Load visited if not round 0
        try:
            with open("visited.blocks.pickle", "r") as f:
                visitedBlocks = cPickle.load(f)
        except Exception as error:
            print('oopsie in writing visited blocks :(')
        # Update visited blocks
        if startPosition not in visitedBlocks:
            visitedBlocks.append(startPosition)
        with open("visited.blocks.pickle", "wb") as f:
            cPickle.dump(visitedBlocks, f)


    #Todo: Testing
    """
    visitedBlocks = [(2, 1), (1, 1)
    """
    #logger.info("already visited: " + str(visitedBlocks))
    firstGameNode.setVisitedBlocks(visitedBlocks)
    firstGameNode.setMyPlayerKey(playerKey)


    #graphTester(firstGameNode, playerKey)
    #print "DONEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEE"
    #sys.exit()

    firstGameNode.guessTarget()
    #print firstGameNode.guessedTarget

    cameFrom, costSoFar, foundKey, startKey = timedGameScoreSearch(firstGameNode, playerKey, timedSearchTimeout)

    #logger.info("found: " + str(foundKey))
    nextNode = foundKey

    targetNode = None
    pathCount = 0
    while nextNode != startKey:
        pathCount += 1
        #logger.info("#############################################  REVERSING")
        #logger.info(expandedNodes[nextNode].getStatePretty())
        #logger.info("reversing: " + str(expandedNodes[nextNode].moveThatLedHere))
        if cameFrom[nextNode] == startKey:
            targetNode = nextNode
            break
        nextNode = cameFrom[nextNode]
    action = moves[expandedNodes[targetNode].moveThatLedHere]




    ### Execute my plan
    executeStartTime = time.time()
    if action == None:
        #logger.info("WTF? Doing nothing")
        action = moves['DoNothing']
    logger.info('Action: {}'.format(ACTIONS[action]))
    with open(os.path.join(output_path, 'move.txt'), 'w') as f:
        f.write('{}\n'.format(action))
    finishedTime = time.time()



def timedGameScoreSearch(graph, playerKey, timeout):
    startPos = graph.getPosition(playerKey)
    counter = 0
    frontier = PriorityQueue()
    graphKey = graph.getStateKey()
    foundKey = None
    frontier.put(graphKey, 0)
    cameFrom = {}
    costSoFar = {}
    startKey = graph.getStateKey()
    expandedNodes[startKey] = graph
    cameFrom[startKey] = None
    costSoFar[startKey] = 0
    bestHeuristicSoFar = 99999
    bestFoundSoFar = startKey
    targetScore = 50

    while not frontier.empty():
        counter += 1
        if counter > 1999: break
        currentKey = frontier.get()
        current = expandedNodes[currentKey]

        if time.time() > timeout:
            foundKey = bestFoundSoFar
            logger.info("breaking because of timeout, counter: " + str(counter))
            break

        #check for goal
        if current.getScore() > targetScore:
            foundKey = currentKey
            logger.info("breaking because found, counter: " + str(counter))
            break

        nCounter = 0
        for next in current.neighbors(playerKey):
            nCounter += 1
            nextKey = next.getStateKey()
            expandedNodes[nextKey] = next
            newCost = costSoFar[currentKey] + 1 #graph.cost(current, next, playerKey)
            if nextKey not in costSoFar or newCost < costSoFar[nextKey]:
                costSoFar[nextKey] = newCost
                heuristic = next.cleverScoreHeuristic(targetScore)
                if heuristic < bestHeuristicSoFar and len(next.neighbors(playerKey)) > 0:
                    bestFoundSoFar = nextKey
                    bestHeuristicSoFar = heuristic
                priority = newCost + heuristic
                cameFrom[nextKey] = currentKey
                if len(next.neighbors(playerKey)) > 0: # add to frontier if I am alive in this NODE
                    #Add large penalty for states where an opponent can blow me up so we only remove from frontier if absolutely nescecerry
                    #get position
                    nextPosition = next.getPosition(playerKey)
                    inOpponentDangerZone = next.testIfInOpponentDanger(nextPosition)
                    #logger.info("inOpponentDangerZone: %s" % inOpponentDangerZone)
                    #check if in simulatedBombZone
                    opponentDangerPenalty = 0
                    if inOpponentDangerZone:
                        opponentDangerPenalty = 999
                    frontier.put(nextKey, priority + opponentDangerPenalty)

    #logger.info("returning from timedGameStarSearch, counter: " + str(counter))
    return cameFrom, costSoFar, foundKey, startKey

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('player_key', nargs='?')
    parser.add_argument('output_path', nargs='?', default=os.getcwd())
    parser.add_argument('--user', nargs='?', default=os.getcwd())
    args = parser.parse_args()
    assert(os.path.isdir(args.output_path))
    main(args.player_key, args.output_path)
    #logger.info("end difference: %s" % (time.time() - startTime))
