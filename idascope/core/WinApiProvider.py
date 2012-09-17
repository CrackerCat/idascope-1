#!/usr/bin/python
########################################################################
# Copyright (c) 2012
# Daniel Plohmann <daniel.plohmann<at>gmail<dot>com>
# Alexander Hanel <alexander.hanel<at>gmail<dot>com>
# All rights reserved.
########################################################################
#
#  This file is part of IDAscope
#
#  IDAscope is free software: you can redistribute it and/or modify it
#  under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful, but
#  WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#  General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see
#  <http://www.gnu.org/licenses/>.
#
########################################################################
# Credits:
# - Thanks to Sascha Rommelfangen for testing / fixing path resolution
#   for OS X.
########################################################################

import json
import os

import JsonHelper


class WinApiProvider():
    """
    Data provider for request concerning WinApi information.
    """

    def __init__(self, idascope_config):
        print ("[|] Loading WinApiProvider")
        self.os = os
        self.idascope_config = idascope_config
        self.winapi_data = {}
        if self.idascope_config.winapi_load_keyword_database:
            self._load_keywords()
        self.last_delivered_filepath = self.idascope_config.winapi_rootdir
        self.backward_history = []
        self.forward_history = []
        self.is_appending_to_history = True

    def _load_keywords(self):
        """
        Loads the keywords database from the file specified in the config.
        """
        keywords_file = open(self.idascope_config.winapi_keywords_file, "r")
        self.winapi_data = json.loads(keywords_file.read(), object_hook=JsonHelper.decode_dict)

    def has_offline_msdn_available(self):
        """
        Determines wther the offline MSDN database is available or not.
        This is evaluated based on whether the keywords database has been loaded or not.
        @return: (bool) availablity of the MSDN database
        """
        if len(self.winapi_data.keys()) > 0:
            return True
        return False

    def get_keywords_for_initial(self, keyword_initial):
        """
        Get all keywords that start with the given initial character.
        @param keyword_initial: an initial character
        @type keyword_initial: str
        @return: (a list of str) keywords in WinApi that start with that initial.
        """
        if keyword_initial in self.winapi_data.keys():
            return sorted(self.winapi_data[keyword_initial], key=str.lower)
        else:
            return []

    def get_keyword_content(self, keyword):
        """
        Get the content for this keyword.
        @type keyword: str
        @return: (str) HTML content.
        """
        api_filenames = self._get_api_filenames(keyword)
        if len(api_filenames) == 1:
            api_filenames = [self.idascope_config.winapi_rootdir + api_filenames[0]]
        return self._get_document_content(api_filenames)

    def get_linked_document_content(self, url):
        """
        Get the content for a requested linked document
        @param url: URL of the requested file
        @type url: QUrl
        @return: a tuple (str, str) with content and anchor within the content
        """
        anchor = ""
        if url.isRelative():
            url_str = url.toString()
            anchor = ""
            document_content = ""
            if "#" in url_str:
                anchor = url_str[1 + url_str.rfind("#"):]
                url_str = url_str[:url_str.rfind("#")]
            if url_str != "":
                filename = self.os.path.join(str(self.last_delivered_filepath), str(url_str))
                document_content = self._get_single_document_content(filename)
            return document_content, anchor
        else:
            return self._get_single_document_content(url.toString()), anchor

    def get_history_states(self):
        """
        Get information about whether history stepping (backward, forward) is available or not.
        @return: a tuple (boolean, boolean) telling about availability of history stepping.
        """
        return (len(self.backward_history) > 1, len(self.forward_history) > 0)

    def get_previous_document_content(self):
        """
        Get the content of the previously accessed document. This implements the well-known "back"-button
        functionality.
        @return: a tuple (str, str) with content and anchor within the content
        """
        self._cleanup_histories()
        # first move latest visited document to forward queue.
        if len(self.backward_history) > 0:
            history_entry = self.backward_history.pop()
            self.forward_history.append(history_entry)
            # obtain former penultimate document from history and return its content
            if len(self.backward_history) > 0:
                self.is_appending_to_history = False
                history_entry = self.backward_history[-1]
                document_content = self._get_document_content(history_entry[0]), history_entry[1]
                self.is_appending_to_history = True
                return document_content
        return ("", "")

    def get_next_document_content(self):
        """
        Get the content of the previously accessed document. This implements the well-known "back"-button
        functionality.
        @return: a tuple (str, str) with content and anchor within the content
        """
        # first move latest visited document again to backward queue.
        self._cleanup_histories()
        if len(self.forward_history) > 0:
            history_entry = self.forward_history.pop()
            self.backward_history.append(history_entry)
            self.is_appending_to_history = False
            document_content = self._get_document_content(history_entry[0]), history_entry[1]
            self.is_appending_to_history = True
            return document_content
        return ("", "")

    def _cleanup_histories(self):
        """
        Eliminate subsequent similar items from history lists
        """
        self.backward_history = self._cleanup_list(self.backward_history)
        self.forward_history = self._cleanup_list(self.forward_history)

    def _cleanup_list(self, input_list):
        """
        Eliminate subsequent similar items from a list
        @param input_list: A list of arbitrary items
        @type input_list: list
        @return: (list) the input list without subsequent similar items
        """
        cleaned_list = []
        last_entry = None
        for entry in input_list:
            if entry != last_entry:
                cleaned_list.append(entry)
            last_entry = entry
        return cleaned_list

    def _get_api_filenames(self, keyword):
        """
        Get filenames that are associated with the given keyword.
        @param keyword: keyword to get the filenames for
        @type keyword: str
        @return: (a list of str) filenames that cover this keyword.
        """
        if len(keyword) > 0:
            keyword_initial = keyword[0].lower()
            if keyword_initial in self.winapi_data.keys():
                if keyword in self.winapi_data[keyword_initial]:
                    return self.winapi_data[keyword_initial][keyword]
        return []

    def _get_document_content(self, filenames):
        """
        Produce the document content for a given list of filenames.
        If there are multiple filenames, no document content is returned but a rendered list fo the filenames,
        @param filenames: the filename(s) to get content for
        @type filenames: list of str
        @return: (str) HTML content.
        """
        document_content = "<p>No entries for your query.</p>"
        if len(filenames) > 1:
            document_content = self._generate_html_list_of_filenames(filenames)
            if self.is_appending_to_history:
                self.forward_history = []
                self.backward_history.append((filenames, ""))
                self._cleanup_histories()
        elif len(filenames) == 1:
            document_content = self._get_single_document_content(filenames[0])
        return document_content

    def _generate_html_list_of_filenames(self, filenames):
        """
        Convert a list of filenames as string into a mini-HTML document with the list entries as links to the files
        in a bullet list.
        @param filenames: the filenames to include in the bullet list
        @type filenames: list of str
        @return: (str) a HTML file with a bullet list of links to the filenames
        """
        document_content = "<p>Multiple files are covering this keyword. Choose one:</p><ul>"
        for filename in filenames:
            # sanitize filenames as obtained from the config file.
            filename = filename.replace('\\', self.os.sep)
            document_content += "<li><a href=\"%s\">%s</a></li>" % (self.idascope_config.winapi_rootdir + \
                filename, filename)
        return document_content

    def _get_single_document_content(self, filename):
        """
        Load a single document by filename and return its content.
        @param filename: the filename to load
        @type filename: str
        @return: (str) the content of the file
        """
        document_content = ""
        try:
            # sanitize the filename as obtained from the config file.
            filename = filename.replace('\\', self.os.sep)
            with open(filename, "r") as f:
                document_content = f.read()
                self.last_delivered_filepath = filename[:filename.rfind(self.os.sep)] + self.os.sep
            if self.is_appending_to_history:
                self.forward_history = []
                self.backward_history.append(([filename], ""))
                self._cleanup_histories()
        except Exception as exc:
            document_content = "<html><head /><body>Well, something has gone wrong here. Try again with some" \
                + " proper API name.<hr /><p>Exception: %s</p></body></html>" % exc
        return document_content