#!/usr/bin/env python
# -*- encoding: utf-8 -*-

# Copyright 2018, Nigel Small
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


from neo4j.v1 import urlparse
from prompt_toolkit.layout import UIContent

from agentsmith.controls.data import DataControl


class StyleList(object):

    def __init__(self):
        self.assigned_styles = {}
        self.unassigned_styles = {
            "fg:ansiwhite bg:ansiblue",
            "fg:ansiwhite bg:ansicyan",
            "fg:ansiwhite bg:ansimagenta",
            "fg:ansiwhite bg:ansiyellow",
        }

    def assign_style(self, key):
        if key not in self.assigned_styles and self.unassigned_styles:
            assigned_style = sorted(self.unassigned_styles)[0]
            self.unassigned_styles.remove(assigned_style)
            self.assigned_styles[key] = assigned_style
        return self.assigned_styles.get(key)

    def unassign_style(self, address):
        if address in self.assigned_styles:
            assigned_style = self.assigned_styles[address]
            self.unassigned_styles.add(assigned_style)
            del self.assigned_styles[address]
            return assigned_style
        return None


class OverviewControl(DataControl):

    server_roles = [
        u"LEADER",
        u"FOLLOWER",
        u"READ_REPLICA",
    ]

    def __init__(self, address, auth, style_list, key_bindings=None):
        super(OverviewControl, self).__init__(address, auth, prefer_routing=True, key_bindings=key_bindings)
        self.style_list = style_list
        self.mode = None
        self.servers = dict.fromkeys(self.server_roles, [])
        self.max_width = 0
        self.padding = 0
        # TODO: selected_address, instead of these two
        self.selected_role = u"LEADER"
        self.selected_index = 0

    def preferred_width(self, max_available_width):
        return self.max_width

    def on_refresh(self, data):
        if data is None:
            self.invalidate.fire()
            return
        self.mode = data.system.dbms.mode
        if self.mode in (u"CORE", u"READ_REPLICA"):
            overview = data.cluster_overview
            widths = [0]
            for role in self.servers:
                self.servers[role] = [urlparse(server[u"addresses"][0]).netloc
                                      for server in overview if server[u"role"] == role]
                widths.extend(map(len, self.servers[role]))
            self.max_width = max(widths)
        else:
            self.servers[u"LEADER"] = [self.address]
            self.max_width = len(self.address)
        self.padding = 6 if self.max_width % 2 == 0 else 5
        self.max_width += self.padding
        self.invalidate.fire()

    def on_error(self, error):
        pass # print(error)

    def create_content(self, width, height):
        lines = []

        def append_servers(role):
            for i, address in enumerate(self.servers[role]):
                address_style = self.style_list.assigned_styles.get(address, "")
                if role == self.selected_role and i == self.selected_index:
                    lines.append([
                        ("", " "),
                        (address_style, "  "),
                        ("", " "),
                        ("fg:ansiblack bg:ansigray", address.ljust(width - self.padding)),
                        ("", " "),
                    ])
                else:
                    lines.append([
                        ("", " "),
                        (address_style, "  "),
                        ("", " "),
                        ("", address.ljust(width - self.padding)),
                        ("", " "),
                    ])

        if self.servers[u"LEADER"]:
            if self.for_cluster_core:
                lines.append([("fg:#A0A0A0", " Leader".ljust(width))])
            else:
                lines.append([("fg:#A0A0A0", " Server".ljust(width))])
            append_servers(u"LEADER")
            lines.append([])
        if self.servers[u"FOLLOWER"]:
            lines.append([("fg:#A0A0A0", " Followers".ljust(width))])
            append_servers(u"FOLLOWER")
            lines.append([])
        if self.servers[u"READ_REPLICA"]:
            lines.append([("fg:#A0A0A0", " Read replicas".ljust(width))])
            append_servers(u"READ_REPLICA")
            lines.append([])

        def get_line(y):
            return lines[y]

        return UIContent(
            get_line=get_line,
            line_count=len(lines),
            show_cursor=False,
        )

    @property
    def selected_address(self):
        try:
            return self.servers[self.selected_role][self.selected_index]
        except IndexError:
            return self.address

    def add_highlight(self):
        return self.style_list.assign_style(self.selected_address)

    def remove_highlight(self):
        return self.style_list.unassign_style(self.selected_address)

    def home(self, event):
        if not self.servers[self.selected_role]:
            return False
        selected_role = self.server_roles[0]
        selected_index = 0
        if selected_role != self.selected_role or selected_index != self.selected_index:
            self.selected_role = selected_role
            self.selected_index = selected_index
            return True
        else:
            return False

    def end(self, event):
        if not self.servers[self.selected_role]:
            return False
        y = -1
        while not self.servers[self.server_roles[y]]:
            y -= 1
        selected_role = self.server_roles[y]
        selected_index = len(self.servers[self.selected_role]) - 1
        if selected_role != self.selected_role or selected_index != self.selected_index:
            self.selected_role = selected_role
            self.selected_index = selected_index
            return True
        else:
            return False

    def page_up(self, event):
        if not self.servers[self.selected_role]:
            return False
        self.selected_index -= 1
        while self.selected_index < 0:
            old_role_index = self.server_roles.index(self.selected_role)
            new_role_index = (old_role_index - 1) % len(self.server_roles)
            self.selected_role = self.server_roles[new_role_index]
            self.selected_index = len(self.servers[self.selected_role]) - 1
        return True

    def page_down(self, event):
        if not self.servers[self.selected_role]:
            return False
        self.selected_index += 1
        while self.selected_index >= len(self.servers[self.selected_role]):
            old_role_index = self.server_roles.index(self.selected_role)
            new_role_index = (old_role_index + 1) % len(self.server_roles)
            self.selected_role = self.server_roles[new_role_index]
            self.selected_index = 0
        return True
