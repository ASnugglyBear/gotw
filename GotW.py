import logging
from datetime import date
import re

from boardgamegeek import BoardGameGeek as BGG

log = logging.getLogger('gotw')

def getNotFoundGames(games):
    '''take a list of games and return those that are not found.'''
    bgg = BGG()
    not_found = []
    for game in games:
        try:
            log.info(u'Looking for {} on BGG.'.format(game))
            found = bgg.game(game)
        except boardgamegeek.exceptions.BoardGameGeekError as e:
            log.critical(u'Error talking to BGG about {}'.format(game))
            continue

        if not found:
            log.warning(u'Unable to find {} on BGG'.format(game))
            not_found.append(game)

    return not_found


def getGotWPostText(game_name, next_game_name):
    '''Take the name of a game, and return the GotW text to post to Reddit'''
    bgg = BGG()
    try:
        game = bgg.game(game_name)
    except boardgamegeek.exceptions.BoardGameGeekError as e:
        log.critical(u'Error getting info from BGG on {}: {}'.format(
            game_name, e))
        return None

    if not game:
        log.critical(u'Unable to find {} on BGG'.format(game_name))
        return None

    text = u'[//]: # (GOTWS)\n'
    text += (u'This week\'s game is [**{}**](http:{})\n\n'.format(game.name, game.image))
    text += u' * **BGG Link**: [{}](http://www.boardgamegeek.com/boardgame/{})\n'.format(
        game.name, game.id)

    designers = getattr(game, u'designers', [u'Unknown'])
    plural = u's' if len(designers) > 1 else u''
    text += u' * **Designer{}**: {}\n'.format(plural, ', '.join(designers))
    
    publishers = getattr(game, u'publishers', [u'Unknown'])
    plural = u's' if len(publishers) > 1 else u''
    text += u' * **Publisher{}**: {}\n'.format(plural, ', '.join(publishers))
    
    text += u' * **Year Released**: {}\n'.format(game.year)
    
    mechanics = getattr(game, u'mechanics', [u'Unknown'])
    plural = u's' if len(mechanics) > 1 else u''
    text += u' * **Mechanic{}**: {}\n'.format(plural, ', '.join(mechanics))
    
    if game.min_players == game.max_players:
        players = '{}'.format(game.min_players)
    else:
        players = '{} - {}'.format(game.min_players, game.max_players)
    text += u' * **Number of Players**: {}\n'.format(players)
    
    text += u' * **Playing Time**: {} minutes\n'.format(game.playing_time)
    
    expansions = getattr(game, 'expansions', None)
    if expansions:
        text += u' * **Expansions**: {}\n'.format(', '.join([e.name for e in expansions]))

    text += u' * **Ratings**:\n'
    people = u'people' if game.users_rated > 1 else u'person'
    text += u'    * Average rating is {} (rated by {} {})\n'.format(
        game.rating_average, game.users_rated, people)
    ranks = u', '.join([u'{}: {}'.format(
        r[u'friendlyname'], r[u'value']) for r in game.ranks])
    text += u'    * {}\n'.format(ranks)

    text += u'\n\n'

    text += u'**Description from Boardgamegeek**:\n\n{}\n\n'.format(game.description)

    text += u'[//]: # (GOTWE)\n\n'
    text += '---------------------\n\n'

    if not next_game_name:
        text += u'There is no Game of the Week scheduled for next week.'
    else:
        try:
            game = bgg.game(next_game_name)
        except boardgamegeek.exceptions.BoardGameGeekError as e:
            log.critical(u'Error getting info from BGG on {}: {}'.format(
                next_game_name, e))

        if not game:
            text += u'Next Week: {}'.format(next_game_name)
        else:
            text += (u'Next Week: [**{}**](http://www.boardgamegeek'
                     u'.com/boardgame/{})\n\n'.format(game.name, game.id))

    return text

def updateGotWWiki(page, gotws, post_id):
    ### update the wiki page.
    # remove the gotw from the calendar
    search_for = u'\[//]:\s\(CALS\)\s.+\[//]:\s\(CALE\)\s'
    new_cal_list = u''.join([u' * {}\n'.format(g) for g in gotws[1:]])
    new_cal = u'[//]: (CALS)\n' + new_cal_list + u'[//]: (CALE)\n'
    new_wiki_page = re.sub(search_for, new_cal, page, flags=re.DOTALL)

    if new_wiki_page == page:
        log.error(u'Error updating the calenda on the wiki page.')
        return None

    # load up the archive, add this week's gotw, sort by date, subs in the new list.
    games = re.findall(u'(\d{4}-\d{2}-\d{2}) : \[([^\]]+)\]\(/(\w+)\)', new_wiki_page)
    if not games:
        log.critical(u'Unable to find archived GOTW links in wiki page')
        return None

    # add the new game to the archive list.
    games.append([u'{}'.format(date.today()), gotws[0], post_id])

    # now write them out and subst into wiki page.
    # (sort by name for reinsertion)
    games = sorted(games, key=lambda x: x[1])
    new_arch_list = u''.join([u' * {} : [{}](/{})\n'.format(g[0], g[1], g[2]) for g in games])
    new_arch = u'[//]: (GOTWS)\n' + new_arch_list + u'[//]: (GOTWE)\n'
    search_for = u'\[//]:\s\(GOTWS\)\s.+\[//]:\s\(GOTWE\)\s'
    new_wiki = re.sub(search_for, new_arch, new_wiki_page, flags=re.DOTALL)

    return new_wiki

def updateGotWSidebar(sidebar, game_name, post_id):
    # update in two places. The linkbar and the sidebar. 
    # link bar is not distinguished by a comment, but does have
    # "[Game of the Week:..." which we can search for.
    new_sb = re.sub(u'\[Game of the Week:[^\]]+\]\(/\w+\)\s', 
                    u'[Game of the Week: {}](/{}) '.format(game_name, post_id), 
                    sidebar,
                    flags=re.DOTALL)
    
    if new_sb == sidebar:
        log.error(u'Error updating GOTW in linkbar.')
        return sidebar

    # sidebar link ends with " [//]: # (GOTWLINK)"
    new_new_sb = re.sub(u'\[//\]: # \(GOTWLINK\)\n\[[^\]]+\]\(/\w+\)',
                        u'[//]: # (GOTWLINK)\n[{}](/{})'.format(game_name, post_id), 
                        new_sb,
                        flags=re.DOTALL)

    if new_new_sb == new_sb:
        log.error(u'Error updating GOTW in link in sidebar.')
        return sidebar

    return new_new_sb
