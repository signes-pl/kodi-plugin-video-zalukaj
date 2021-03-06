# -*- coding: utf-8 -*-
import json
import logging
import sys
from base64 import b64encode, b64decode

import routing
import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
from resources.lib import kodilogging
from resources.lib.kodiutils import notification, get_setting_as_bool, get_setting
from resources.lib.zalukaj import Zalukaj, ZalukajError
from xbmcgui import ListItem
from xbmcplugin import setResolvedUrl, addDirectoryItem, endOfDirectory

ADDON = xbmcaddon.Addon()

# Get the plugin url in plugin:// notation.
_url = sys.argv[0]

# Get the plugin handle as an integer number.
_handle = int(sys.argv[1])

# Path to keep data files
DATAPATH = xbmc.translatePath(ADDON.getAddonInfo('profile')).decode('utf-8')

logger = logging.getLogger(ADDON.getAddonInfo('id'))
kodilogging.config()
plugin = routing.Plugin()

zalukaj = Zalukaj(DATAPATH)

data_is_login = get_setting_as_bool('zalukaj_login')
data_username = get_setting('zalukaj_username')
data_password = get_setting('zalukaj_password')

data_video_quality = get_setting('video.quality')
data_video_version = get_setting('video.version')


def logout():
    zalukaj.logout()


def login():
    """
    Login into defined account if user is not logged in already.
    """

    current_user = zalukaj.fetch_user_data()
    if zalukaj.fetch_user_data().is_logged():
        return current_user

    current_user = zalukaj.login(user=data_username, password=data_password)
    if current_user.is_logged():
        notification(
            header='[COLOR green]Zalogowano[/COLOR]',
            message="Witaj %s" % current_user.name,
            time=5000
        )
    else:
        notification(
            header='[COLOR red]Błąd logowania[/COLOR]',
            message="Podczas logowania wystąpił problem.",
            time=5000
        )

    return current_user


@plugin.route('/')
def index():
    xbmcplugin.setContent(_handle, 'movies')

    if data_is_login:
        try:
            user = login()
            if user.is_logged() and user.is_premium():
                addDirectoryItem(plugin.handle, plugin.url_for(show_account),
                                 ListItem("%s - %s" % (user.name.lower(), user.account_type)), True)
                addDirectoryItem(plugin.handle, plugin.url_for(show_tv_series_list),
                                 ListItem("[COLOR=lime]Seriale[/COLOR]"), True)
                addDirectoryItem(plugin.handle, plugin.url_for(show_movies_section_list, "kind"),
                                 ListItem("[COLOR=lime]Filmy - gatunki[/COLOR]"), True)
                addDirectoryItem(plugin.handle, plugin.url_for(show_search),
                                 ListItem("[COLOR=gold]Szukaj[/COLOR]"), True)
        except ZalukajError as e:
            notification(header='[COLOR red]Błąd[/COLOR]', message=e.message, time=5000)
    else:
        xbmcgui.Dialog().ok("[COLOR red]Dostęp tylko dla konta VIP[/COLOR]",
                            "Aktualnie wtyczka dostępna tylko dla zalogowanych.",
                            "Aby oglądać filmy zaloguj się w ustawieniach tego dodatku.")
        logout()

    # addDirectoryItem(plugin.handle, plugin.url_for(show_movies_section_list, "popularity"),
    #                  ListItem("Filmy - najpopularniejsze"), True)
    # addDirectoryItem(plugin.handle, plugin.url_for(show_movies_section_list, "popularity"),
    #                  ListItem("Filmy - ostatnio dodane"), True)
    # addDirectoryItem(plugin.handle, plugin.url_for(show_movies_section_list, "popularity"),
    #                  ListItem("Filmy - ostatnio oglądane"), True)

    endOfDirectory(plugin.handle)


@plugin.route('/tv-series')
def show_tv_series_list():
    xbmcplugin.setContent(_handle, 'tvshows')

    try:
        for item in zalukaj.fetch_tv_series_list():
            addDirectoryItem(plugin.handle, plugin.url_for(show_tv_series_seasons_list, b64encode(item['url'])),
                             ListItem(item['title']), True)
    except ZalukajError as e:
        notification(header='[COLOR red]Błąd[/COLOR]', message=e.message, time=5000)

    endOfDirectory(plugin.handle)


@plugin.route('/tv-series/seasons/<link_decoded>')
def show_tv_series_seasons_list(link_decoded):
    xbmcplugin.setContent(_handle, 'seasons')

    try:
        link = b64decode(link_decoded)
        for item in zalukaj.fetch_tv_series_seasons_list(link):
            list_item = ListItem(item['title'])
            list_item.setArt({"thumb": item['img'], "poster": item['img'], "banner": item['img'], "icon": item['img'],
                              "landscape": item['img'], "clearlogo": item['img'], "fanart": item['img']})

            addDirectoryItem(plugin.handle, plugin.url_for(show_tv_series_episodes_list,
                                                           b64encode(item['url'])), list_item, True)
    except ZalukajError as e:
        notification(header='[COLOR red]Błąd[/COLOR]', message=e.message, time=5000)
    endOfDirectory(plugin.handle)


@plugin.route('/tv-series/episodes/<link_decoded>')
def show_tv_series_episodes_list(link_decoded):
    xbmcplugin.setContent(_handle, 'episodes')

    try:
        link = b64decode(link_decoded)
        for item in zalukaj.fetch_tv_series_episodes_list(link):
            list_item = ListItem(item['title'])
            list_item.setArt({"thumb": item['img'],
                              "poster": item['img'],
                              "banner": item['img'],
                              "icon": item['img'],
                              "landscape": item['img'],
                              "clearlogo": item['img'],
                              "fanart": item['img']})
            list_item.setInfo('video', {"season": item['season'], "episode": item['episode']})
            list_item.setProperty('IsPlayable', 'true')

            addDirectoryItem(plugin.handle, plugin.url_for(play_movie, b64encode(item['url'])), list_item)
    except ZalukajError as e:
        notification(header='[COLOR red]Błąd[/COLOR]', message=e.message, time=5000)
    endOfDirectory(plugin.handle)


@plugin.route('/play/<link_decoded>')
def play_movie(link_decoded):
    xbmcplugin.setContent(_handle, 'movies')

    try:
        link = b64decode(link_decoded)
        data = zalukaj.fetch_movie_details(link)
        streams = data['streams']
        versions = data['versions']

        if versions and len(versions) > 1:
            selected_version = xbmcgui.Dialog().select("Wybór wersji wideo", [item['version'] for item in versions])
            data = zalukaj.fetch_movie_from_player(versions[selected_version]['url'])
            streams = data['streams']

        if not streams or len(streams) == 0:
            notification(header='[COLOR red]Błąd odtwarzania[/COLOR]', message="Nie można odtworzyć filmu.", time=5000)
            setResolvedUrl(plugin.handle, False, ListItem(path=''))

        movie_url = streams[0]['url']

        if len(streams) > 1:
            selected_quality = xbmcgui.Dialog().select("Wybór jakości wideo", [item['quality'] for item in streams])
            movie_url = streams[selected_quality]['url']

        setResolvedUrl(plugin.handle, True, ListItem(path=movie_url))

    except ZalukajError as e:
        notification(header='[COLOR red]Błąd[/COLOR]', message=e.message, time=5000)


@plugin.route('/account')
def show_account():
    user = zalukaj.fetch_user_data()
    if user.is_logged():
        addDirectoryItem(plugin.handle, "", ListItem("Hello user %s!" % user.name))
    endOfDirectory(plugin.handle)


@plugin.route('/movies/<section>')
def show_movies_section_list(section):
    try:
        if section == "kind":
            for item in zalukaj.fetch_movie_categories_list():
                addDirectoryItem(plugin.handle,
                                 plugin.url_for(show_movies_list, b64encode(item['url'])),
                                 ListItem(item['title']),
                                 True)

    except ZalukajError as e:
        notification(header='[COLOR red]Błąd[/COLOR]', message=e.message, time=5000)

    endOfDirectory(plugin.handle)


@plugin.route('/movies-list/<link_decoded>')
def show_movies_list(link_decoded):
    xbmcplugin.setContent(_handle, 'movies')

    try:
        link = b64decode(link_decoded)
        for item in zalukaj.fetch_movies_list(link):
            list_item = ListItem(item['title'])
            if 'img' in item:
                list_item.setArt({"thumb": item['img'],
                                  "poster": item['img'],
                                  "banner": item['img'],
                                  "icon": item['img'],
                                  "landscape": item['img'],
                                  "clearlogo": item['img'],
                                  "fanart": item['img']})

            if 'nav' not in item:
                list_item.setProperty('IsPlayable', 'true')
                list_item.setInfo('video', {
                    "year": item.get('year', None),
                    "plot": item.get('description', ''),
                    "plotoutline": item.get('description', ''),
                    "title": item['title'],
                })
                addDirectoryItem(plugin.handle,
                                 plugin.url_for(play_movie, b64encode(item['url'])),
                                 list_item)
            else:
                addDirectoryItem(plugin.handle,
                                 plugin.url_for(show_movies_list, b64encode(item['url'])),
                                 list_item,
                                 True)
    except ZalukajError as e:
        notification(header='[COLOR red]Błąd[/COLOR]', message=e.message, time=5000)
    endOfDirectory(plugin.handle)


@plugin.route('/search')
def show_search():
    xbmcplugin.setContent(_handle, 'movies')
    try:
        search_phrase = xbmcgui.Dialog().input('Szukaj filmu', type=xbmcgui.INPUT_ALPHANUM)
        if search_phrase:
            for item in zalukaj.search_movies(search_phrase):
                list_item = ListItem(item['title'])
                if 'img' in item:
                    list_item.setArt({"thumb": item['img'],
                                      "poster": item['img'],
                                      "banner": item['img'],
                                      "icon": item['img'],
                                      "landscape": item['img'],
                                      "clearlogo": item['img'],
                                      "fanart": item['img']})

                list_item.setInfo('video', {
                    "year": item.get('year', None),
                    "plot": item.get('description', ''),
                    "plotoutline": item.get('description', ''),
                    "title": item['title'],
                })

                if item.get('tv_series') is True:
                    addDirectoryItem(plugin.handle,
                                     plugin.url_for(show_tv_series_seasons_list, b64encode(item['url'])),
                                     list_item,
                                     True)
                else:
                    list_item.setProperty('IsPlayable', 'true')
                    addDirectoryItem(plugin.handle,
                                     plugin.url_for(play_movie, b64encode(item['url'])),
                                     list_item)

    except ZalukajError as e:
        notification(header='[COLOR red]Błąd[/COLOR]', message=e.message, time=5000)
    endOfDirectory(plugin.handle)


def run():
    plugin.run()
