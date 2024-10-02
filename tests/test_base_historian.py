# -*- coding: utf-8 -*- {{{
# ===----------------------------------------------------------------------===
#
#                 Installable Component of Eclipse VOLTTRON
#
# ===----------------------------------------------------------------------===
#
# Copyright 2022 Battelle Memorial Institute
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy
# of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
# ===----------------------------------------------------------------------===
# }}}

from time import sleep

from historian.base import BaseHistorianAgent


class ConcreteHistorianAgent(BaseHistorianAgent):
    def __init__(self, **kwargs):
        super(ConcreteHistorianAgent, self).__init__(**kwargs)
        self._published_list_items = []
        self.start_process_thread()
        sleep(0.5)

    def publish_to_historian(self, to_publish_list):
        self._published_list_items.append(to_publish_list)

    def get_publish_list(self):
        return self._published_list_items

    def reset_publish_list_items(self):
        self._published_list_items.clear()

    def has_published_items(self):
        return len(self._published_list_items) > 0


def test_cache_enable():
    # now = format_timestamp(datetime.utcnow())
    # headers = {
    #     header_mod.DATE: now,
    #     header_mod.TIMESTAMP: now
    # }
    agent = ConcreteHistorianAgent(cache_only_enabled=True)
    assert agent is not None
    device = "devices/testcampus/testbuilding/testdevice"
    agent._capture_data(peer="foo",
                        sender="test",
                        bus="",
                        topic=device,
                        headers={},
                        message={"OutsideAirTemperature": 52.5, "MixedAirTemperature": 58.5},
                        device=device
                        )
    sleep(0.1)
    # Should not have published to the concrete historian because we are in cache_only
    assert not agent.has_published_items()
