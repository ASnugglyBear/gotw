import logging
import argparse
import re
from sys import exit
from html import unescape, escape  # python 3.4+

import praw

from ArgParseLogging import addLoggingArgs, handleLoggingArgs
from GotW import getGotWPostText, updateGotWWiki, updateGotWSidebar, getNotFoundGames


log = logging.getLogger('gotw')

if __name__ == '__main__':
    '''A simple script that posts the game of the week for /r/boardgames'''
    ap = argparse.ArgumentParser()
    ap.add_argument(u'-w', u'--wiki', help=u'The wiki page from which to read/write the calendar info') 
    ap.add_argument(u'-s', u'--subreddit', help=u'The subreddit to update. Must have the gotw wiki '
                    u'page.')
    addLoggingArgs(ap)
    args = ap.parse_args()
    handleLoggingArgs(args)

    wiki_path = args.wiki if args.wiki else u'game_of_the_week'
    subreddit = args.subreddit if args.subreddit else u'boardgames'

    reddit = praw.Reddit(u'Game of the Week poster for /r/boardgames by /u/phil_s_stien')
    reddit.login()  # use ambient praw.ini or stdin/getpass

    gotw_wiki = reddit.get_wiki_page(subreddit, wiki_path)
    log.debug(u'got wiki data: {}'.format(gotw_wiki.content_md))

    # finding the next GOTW is done in two parts. Find the wiki chunk, then find the list 
    # of games within that chunk
    search_for = u'\[//]:\s\(CALS\)\s+\s+\*\s+.*\[//]:\s\(CALE\)'
    match = re.search(search_for, gotw_wiki.content_md, flags=re.DOTALL)
    if not match:
        log.critical(u'Unable to find the upcoming GOTW in the wiki page "{}". Are there embedded'
                     u' delimiters in the page [//]: (CALS) and [//]: (CALE)?'.format(wiki_path))
        reddit.send_message(u'#' + subreddit, subject=u'Unable to post GotW',
                            message=u'There was a problem posting the GotW. Take a look at '
                                    u'the gotw wiki page. There is something amiss.')
        exit(1)

    cal_games = re.findall(u'\*\s+(.*)\s+', match.group(0))
    if not cal_games:
        log.critical(u'There are no games of the week queued up. Nothing to do.')
        exit(2)

    cal_games = [g.rstrip('\r\n') for g in cal_games]

    # first confirm the games are searchable. If not give up!
    not_found = getNotFoundGames(cal_games)
    if not_found:
       log.info(u'Sending mod mail. We could not find game(s) {}'.format(', '.join(not_found)))
       reddit.send_message(u'#' + subreddit, subject=u'Error in GotW Calendar',
                           message=u'Could not find the following game(s) on BGG: {}'
                                   u'. Please fix the GotW wiki calendar and re-run the GotW '
                                   u' script.'.format(', '.join(not_found)))
       log.critical(u'Games on calendar not found. Bailing.')
       exit(3)


    next_gotw_name = cal_games[1] if len(cal_games) >= 2 else None
    log.info(u'found next game of the week: {}. Followed by {}'.format(
        cal_games[0], next_gotw_name))

    # get the text of the GotW post.
    title, post_text = getGotWPostText(cal_games[0], next_gotw_name)

    if not post_text:
        log.critical(u'Error getting GotW post text')
        exit(4)

    # log.debug(u'Posting gotw text: {}'.format(post_text))
    post = reddit.submit(subreddit, title=title, text=post_text)
    post.distinguish(as_made_by=u'mod')
    log.info(u'Submitted gotw post for {}.'.format(cal_games[0]))

    # remind mods if fewer than 3 games left in calendar
    if len(cal_games) <= 2:
        log.info(u'Sending mod mail as there are fewer than 3 games in the GotW queue.')
        reddit.send_message(u'#' + subreddit, subject=u'Top up the GotW Calendar', 
                            message=u'Fewer than three games on the GotW. Please add more.')

    new_wiki_page = updateGotWWiki(unescape(gotw_wiki.content_md), cal_games, post.id)
    if not new_wiki_page:
        log.critical(u'Unable to update GotW wiki page for some reason.')
        exit(5)

    reddit.edit_wiki_page(subreddit=subreddit, page=wiki_path, content=new_wiki_page,
                          reason=u'GotW post update for {}'.format(cal_games[0]))
    log.info(u'GotW wiki information updated.')

    # finally update the sidebar/link menu
    sidebar = unescape(reddit.get_subreddit(subreddit).get_settings()["description"])
    new_sidebar = updateGotWSidebar(sidebar, cal_games[0], next_gotw_name, post.id)
    if new_sidebar == sidebar:
        log.critical(u'Error updating the sidebar for GotW.')
        exit(6)
    
    reddit.get_subreddit(subreddit).update_settings(description=new_sidebar)
    log.info(u'Sidebar updated with new GotW information.')

    exit(0)  # success!
