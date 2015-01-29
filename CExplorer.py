#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2014, Cristian García <cristian99garcia@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

import os
import globals as G

from gi.repository import Gtk
from gi.repository import GObject

from widgets import View
from widgets import InfoBar
from widgets import Notebook
from widgets import PlaceBox
from widgets import StatusBar
from widgets import LateralView
from widgets import PropertiesWindow


class CExplorer(Gtk.Window):

    def __init__(self):
        Gtk.Window.__init__(self)

        self.dirs = G.Dirs()
        self.folder = G.HOME_DIR
        self.folder_name = self.dirs[self.folder]
        self.other_view = False
        self.view = None
        self.icon_size = G.DEFAULT_ICON_SIZE
        self.pressed_keys = []
        self.shortcut = ''

        self.vbox = Gtk.VBox()

        self.infobar = InfoBar()
        self.vbox.pack_start(self.infobar, False, False, 0)

        self.paned = Gtk.HPaned()
        self.vbox.pack_start(self.paned, True, True, 2)

        self.resize(620, 480)
        self.set_title(self.folder_name)

        self.notebook = Notebook()
        self.new_page()
        self.notebook.connect('switch-page', self.__switch_page)
        self.notebook.connect('new-page', lambda w, p: self.new_page(p))
        self.notebook.connect('remove-page', self.__remove_page_from_notebook)
        self.paned.pack2(self.notebook, True)

        self.place_box = PlaceBox()
        self.place_box.connect('go-up', self.go_up)
        self.place_box.connect('change-directory', self.__item_selected)
        self.set_titlebar(self.place_box)

        self.lateral_view = LateralView()
        self.lateral_view.connect('item-selected', self.__item_selected)
        self.lateral_view.connect('new-page', lambda l, p: self.new_page(p))
        self.lateral_view.connect('show-properties',
            lambda l, p: self.show_properties_for_paths(None, [p]))
        self.lateral_view.select_item(G.HOME_DIR)
        self.paned.pack1(self.lateral_view, False, True)

        self.scan_folder = G.ScanFolder(self.folder)
        self.scan_folder.connect('files-changed', self.update_icons)

        self.statusbar = StatusBar()
        self.statusbar.connect('icon-size-changed', self.__icon_size_changed)
        self.vbox.pack_start(self.statusbar, False, False, 2)

        self.connect('realize', self.__realize_cb)
        self.connect('destroy', self._exit)
        self.connect('key-press-event', self.__key_press_event_cb)
        self.connect('key-release-event', self.__key_release_event_cb)

        self.add(self.vbox)
        self.show_all()
        self.infobar.hide()

    def __realize_cb(self, *args):
        self.place_box.change_mode()

    def __key_press_event_cb(self, widget, event):
        if not event.keyval in self.pressed_keys:
            self.pressed_keys.append(event.keyval)

        shortcut = ''
        for key in self.pressed_keys:
            if key in G.KEYS.keys():
                shortcut += G.KEYS[key] + '+'

        self.shortcut = shortcut[:-1]
        self.check_shortcut()

    def __key_release_event_cb(self, widget, event):
        key = G.KEYS.get(event.keyval, False)
        view = self.get_actual_view()

        if not self.place_box.entry.is_focus():
            if key == 'Enter':
                paths = []

                for path in view.view.get_selected_items():
                    treeiter = view.model.get_iter(path)
                    paths.append(view.get_path_from_treeiter(treeiter))

                self.__item_selected(None, paths)

            elif key == 'Backspace':
                self.go_up()

        if event.keyval in self.pressed_keys:
            self.pressed_keys.remove(event.keyval)

    def __item_selected(self, widget, paths):
        if type(paths) == str:
            paths = [G.clear_path(paths)]

        paths.reverse()
        if not paths:
            return

        if paths[0] != self.folder:
            self.set_folder(paths[0])

        for path in paths[1:]:
            if os.path.isdir(paths[0]):
                self.new_page(path)

    def __switch_page(self, notebook, view, page):
        GObject.idle_add(self.update_widgets, view=view)

    def __remove_page_from_notebook(self, notebook, view):
        idx = self.notebook.get_children().index(view)
        self.remove_page(idx)

    def __icon_size_changed(self, widget, value):
        self.icon_size = value
        for view in self.notebook.get_children():
            GObject.idle_add(view.set_icon_size, value)

    def __update_statusbar(self, view, selection):
        self.statusbar.update_label(view.folder, selection, view.model)

    def __try_rename(self, widget, old_path, new_name):
        readable, writable = G.get_access(old_path)
        new_path = os.path.join(G.get_parent_directory(old_path), new_name)
        if not writable:
            widget.entry.set_text(self.dirs[old_path])
            self.infobar.set_msg(G.ERROR_NOT_UNWRITABLE, old_path)
            self.infobar.show_all()
            return

        if os.path.exists(new_path):
            widget.entry.set_text(self.dirs[old_path])
            self.infobar.set_msg(G.ERROR_ALREADY_EXISTS, new_path)
            self.infobar.show_all()
            return

        if '/' in new_name:
            widget.entry.set_text(self.dirs[old_path])
            self.infobar.set_msg(G.ERROR_INVALID_NAME, new_name)
            self.infobar.show_all()
            return

        os.rename(old_path, new_path)

    def check_shortcut(self):
        if self.shortcut  == 'Ctrl+l':
            self.place_box.change_mode()

        elif self.shortcut == 'Ctrl+w':
            self.remove_page(close=True)

        elif self.shortcut == 'Ctrl+t':
            self.new_page()

        elif self.shortcut == 'Ctrl+h':
            self.scan_folder.set_show_hidden_files(not self.scan_folder.show_hidden_files)

        elif self.shortcut == 'Ctrl+f':
            print 'Search files'

        elif self.shortcut == 'Ctrl+n':
            print 'New window'

        elif self.shortcut == 'Ctrl++':
            print 'Aument'

        elif self.shortcut == 'Ctrl+-':
            print 'Disminuit'

    def remove_page(self, idx=None, view=None, close=False):
        if not view:
            if idx is None:
                idx = self.notebook.get_current_page()

            view = self.notebook.get_children()[idx]

        self.notebook.remove(view)
        if not self.notebook.get_children() and not close:
            self.new_page()

        elif not self.notebook.get_children() and close:
            self._exit()

        self.notebook.set_show_tabs(len(self.notebook.get_children()) > 1)

    def change_place_view(self):
        self.place_box.change_mode()

    def set_folder(self, folder):
        readable, writable = G.get_access(folder)
        if readable and os.path.isdir(folder):
            self.folder = folder
            self.get_actual_view().folder = folder
            self.place_box.set_folder(folder)
            self.scan_folder.set_folder(folder)

        elif os.path.isfile(folder):
            #  Open file
            pass

        elif not os.path.exists(folder):
            self.infobar.set_msg(G.ERROR_NOT_EXISTS, folder)
            self.infobar.show_all()

        elif not readable:
            self.infobar.set_msg(G.ERROR_NOT_PERMISSIONS_READABLE, folder)
            self.infobar.show_all()

        GObject.idle_add(self.update_widgets, force=False)

    def go_up(self, *args):
        self.set_folder(G.get_parent_directory(self.folder))

    def new_page(self, path=''):
        path = G.HOME_DIR if not path else path
        view = self.notebook.create_page_from_path(path)
        view.icon_size = self.icon_size
        view.connect('selection-changed', self.__update_statusbar)
        view.connect('item-selected', self.__item_selected)
        view.connect('item-selected', lambda *args: self.notebook.update_tab_labels())
        view.connect('new-page', lambda x, p: self.new_page(p))
        view.connect('show-properties', self.show_properties_for_paths)

    def show_properties_for_paths(self, view, paths):
        if not paths:
            paths = [self.folder]

        paths.reverse()
        dialog = PropertiesWindow(paths)
        dialog.connect('rename-file', self.__try_rename)
        dialog.set_transient_for(self)

    def update_widgets(self, view=None, force=True):
        # FIXME: hay que fijarse la posición actual con respecto al historial
        #        para poder hacer set_sensitive

        update_icons = False
        if (not view or not isinstance(view, Gtk.ScrolledWindow)) and force:
            view = self.get_actual_view()
            update_icons = True

        self.view = view
        self.other_view = True
        self.folder = view.folder

        GObject.idle_add(self.place_box.set_folder, view.folder)
        #self.place_box.button_left.set_sensitive(bool(view.history))
        #self.place_box.button_right.set_sensitive(bool(view.history))
        self.place_box.button_up.set_sensitive(view.folder != G.SYSTEM_DIR)
        self.lateral_view.select_item(self.folder)
        self.scan_folder.set_folder(view.folder)
        self.scan_folder.scan(force=update_icons)
        self.notebook.update_tab_labels()

    def update_icons(self, scan_folder, paths):
        view = self.get_actual_view()
        GObject.idle_add(view.show_icons, paths)

    def get_actual_view(self):
        if not self.other_view:
            idx = self.notebook.get_current_page()
            return self.notebook.get_children()[idx]

        else:
            self.other_view = False
            return self.view

    def _exit(self, *args):
        #  Check actuals process
        Gtk.main_quit()


if __name__ == '__main__':
    CExplorer()
    Gtk.main()
