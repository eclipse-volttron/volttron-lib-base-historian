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

import random
from abc import abstractmethod
from datetime import datetime, timezone

import gevent
import pytest

from volttron.client.messaging import headers as headers_mod
from volttron.utils import format_timestamp
from volttron.utils.jsonrpc import RemoteError

# Module level variables
DEVICES_ALL_TOPIC = "devices/Building/LAB/Device/all"
MICROSECOND_PRECISION = 0
table_names = dict()
historian_version = ""
connection_type = ""
query_points = {
    "oat_point": "Building/LAB/Device/OutsideAirTemperature",
    "mixed_point": "Building/LAB/Device/MixedAirTemperature",
    "damper_point": "Building/LAB/Device/DamperSignal"
}

float_meta = {'units': 'F', 'tz': 'UTC', 'type': 'float'}
percent_meta = {'units': '%', 'tz': 'UTC', 'type': 'float'}


class HistorianTestInterface:

    @pytest.fixture(scope="module")
    def historian(self):
        """ Inheriting test classes should install an instance of historian for test and return the vip identity and
            microsecond precision used for timestamp field """
        pass

    @abstractmethod
    def cleanup_tables(self, truncate_tables, drop_tables=False):
        """
        truncate or drop the list of tables passed or if no list is passed all tables in db
        """
        pass

    @pytest.fixture(scope="module")
    def fake_agent(self, volttron_instance):
        agent = volttron_instance.build_agent()
        yield agent
        print("In teardown method of fake_agent")
        agent.core.stop()

    def random_uniform(self, a, b):
        """
        Creates a random uniform value for using within our tests.  This function
        will chop a float off at a specific uniform number of decimals.

        :param a: lower bound of range for return value
        :param b: upper bound of range for return value
        :return: A psuedo random uniform float
        :type a: int
        :type b: int
        :rtype: float
        """
        format_spec = "{0:.13f}"
        return float(format_spec.format(random.uniform(a, b)))

    def assert_timestamp(self, result, expected_date, expected_time):
        global MICROSECOND_PRECISION
        print("TIMESTAMP expected ", expected_time)
        print(f"MICROSECOND {MICROSECOND_PRECISION}")
        if expected_time[-6:] == "+00:00":
            expected_time = expected_time[:-6]

        if 0 < MICROSECOND_PRECISION < 6:
            truncate = (6 - MICROSECOND_PRECISION) * -1
            assert (result == expected_date + 'T'
                    + expected_time[:truncate] + '0' *
                    MICROSECOND_PRECISION + '+00:00')

        elif MICROSECOND_PRECISION == 6:
            assert result == expected_date + 'T' + expected_time + '+00:00'
        else:
            # mysql version < 5.6.4
            assert (result == expected_date + 'T' + expected_time[:-7] +
                    '.000000+00:00')

    def test_query(self, historian, fake_agent):
        """
        Test query method with valid inputs. Inserts three points as part
        of all topic and checks if all three got into the database
        Expected result:
        Should be able to query data based on topic name. Result should contain
        both data and metadata
        :param fake_agent: instance of fake volttron agent used to query using rpc
        :param historian: instance of the historian tested
        """
        global query_points, DEVICES_ALL_TOPIC, MICROSECOND_PRECISION
        identity, MICROSECOND_PRECISION = historian

        # Publish fake data. The format mimics the format used by VOLTTRON drivers.
        # Make some random readings.  Random readings are going to be
        # within the tolerance here.
        oat_reading = self.random_uniform(30, 100)
        mixed_reading = oat_reading + self.random_uniform(-5, 5)
        damper_reading = self.random_uniform(0, 100)

        # Create a message for all points.
        all_message = [{'OutsideAirTemperature': oat_reading,
                        'MixedAirTemperature': mixed_reading,
                        'DamperSignal': damper_reading},
                       {'OutsideAirTemperature': float_meta,
                        'MixedAirTemperature': float_meta,
                        'DamperSignal': percent_meta
                        }]

        # Create timestamp
        now = format_timestamp(datetime.now(timezone.utc))

        # now = '2015-12-02T00:00:00'
        headers = {
            headers_mod.DATE: now,
            headers_mod.TIMESTAMP: now
        }
        # Publish messages
        fake_agent.vip.pubsub.publish('pubsub', DEVICES_ALL_TOPIC, headers, all_message).get(timeout=10)

        gevent.sleep(2)

        # Query the historian
        result = fake_agent.vip.rpc.call(identity,
                                         'query',
                                         topic=query_points['oat_point'],
                                         count=20,
                                         order="LAST_TO_FIRST").get(timeout=100)
        print('Query Result', result)
        assert (len(result['values']) == 1)
        (now_date, now_time) = now.split("T")
        self.assert_timestamp(result['values'][0][0], now_date, now_time)
        assert (result['values'][0][1] == oat_reading)
        assert set(result['metadata'].items()) == set(float_meta.items())

        # Query the historian
        result = fake_agent.vip.rpc.call(identity,
                                         'query',
                                         topic=query_points['mixed_point'],
                                         count=20,
                                         order="LAST_TO_FIRST").get(timeout=10)
        print('Query Result', result)
        assert (len(result['values']) == 1)
        (now_date, now_time) = now.split("T")
        self.assert_timestamp(result['values'][0][0], now_date, now_time)
        assert (result['values'][0][1] == mixed_reading)
        assert set(result['metadata'].items()) == set(float_meta.items())

        # Query the historian
        result = fake_agent.vip.rpc.call(identity,
                                         'query',
                                         topic=query_points['damper_point'],
                                         count=20,
                                         order="LAST_TO_FIRST").get(timeout=10)
        print('Query Result', result)
        assert (len(result['values']) == 1)
        (now_date, now_time) = now.split("T")
        self.assert_timestamp(result['values'][0][0], now_date, now_time)
        assert (result['values'][0][1] == damper_reading)
        assert set(result['metadata'].items()) == set(percent_meta.items())

    def test_query_failure(self, historian, fake_agent):
        """
        Test query with invalid input
        :param fake_agent: instance of fake volttron agent used to query
        using rpc
        :param historian: instance of the historian tested
        """

        global query_points, DEVICES_ALL_TOPIC, MICROSECOND_PRECISION
        identity, MICROSECOND_PRECISION = historian

        gevent.sleep(0.5)
        # Query without topic id
        try:
            fake_agent.vip.rpc.call(identity,
                                    'query').get(timeout=15)
        except RemoteError as error:
            print("topic required excinfo {}".format(error))
            assert '"Topic" required' in str(error.message)

    def test_get_topic_list(self, historian, fake_agent):
        """
        Test the get_topic_list api.
        Expected result:
        Should return list of topics
        :param fake_agent: instance of fake volttron agent used to query
        using rpc
        :param historian: instance of the historian tested
        """

        global query_points, DEVICES_ALL_TOPIC, MICROSECOND_PRECISION
        identity, MICROSECOND_PRECISION = historian

        # Publish fake data. The format mimics the format used by VOLTTRON drivers.
        # Make some random readings
        oat_reading = self.random_uniform(30, 100)
        mixed_reading = oat_reading + self.random_uniform(-5, 5)

        # Create a message for all points.
        # publish with new topic and see if topic_list contains those
        all_message = [{'newtopic1': oat_reading,
                        'newtopic2': mixed_reading},
                       {
                        }]

        # Create timestamp
        now = format_timestamp(datetime.now(timezone.utc))

        # now = '2015-12-02T00:00:00'
        headers = {
            headers_mod.DATE: now,
            headers_mod.TIMESTAMP: now
        }
        print("Published time in header: " + now)
        # Publish messages
        fake_agent.vip.pubsub.publish('pubsub', DEVICES_ALL_TOPIC, headers, all_message)

        gevent.sleep(2)

        # Query the historian
        topic_list = fake_agent.vip.rpc.call('platform.historian', 'get_topic_list').get(timeout=100)
        print('Query Result', topic_list)
        assert len(topic_list) >= 2
        expected = ["Building/LAB/Device/newtopic1",
                    "Building/LAB/Device/newtopic2"]
        assert set(expected).issubset(set(topic_list))

    def test_get_topics_by_pattern(self, historian, fake_agent):
        """
        Test the get_topics_by_pattern api with valid inputs.
        Expected result:
        Should return list of topics that match pattern
        :param fake_agent: instance of fake volttron agent used to query
        using rpc
        :param historian: instance of the historian tested
        """
        global query_points, DEVICES_ALL_TOPIC, MICROSECOND_PRECISION
        identity, MICROSECOND_PRECISION = historian

        # Publish fake data. The format mimics the format used by VOLTTRON drivers.
        # Make some random readings
        oat_reading = self.random_uniform(30, 100)
        mixed_reading = oat_reading + self.random_uniform(-5, 5)

        all_message = [{'topic_matchme_1': oat_reading,
                        'topic_matchme_2': mixed_reading},
                       {'topic_matchme_1': float_meta,
                        'topic_matchme_2': float_meta}]

        # Create timestamp
        now = format_timestamp(datetime.now(timezone.utc))

        # now = '2015-12-02T00:00:00'
        headers = {
            headers_mod.DATE: now,
            headers_mod.TIMESTAMP: now
        }
        print("Published time in header: " + now)
        # Publish messages
        fake_agent.vip.pubsub.publish('pubsub', DEVICES_ALL_TOPIC, headers, all_message)

        gevent.sleep(2)

        pattern_1 = r'Building\/LAB\/Device\/topic_matchme.*'
        # Query the historian
        topic_dict = fake_agent.vip.rpc.call('platform.historian',
                                             'get_topics_by_pattern',
                                             topic_pattern=pattern_1).get(timeout=100)
        print('Query Result for pattern1', topic_dict)
        assert len(topic_dict) == 2
        expected = {"Building/LAB/Device/topic_matchme_1",
                    "Building/LAB/Device/topic_matchme_2"}
        assert expected == set(topic_dict)

        pattern_1 = r'Building\/LAB\/Device\/.*matchme_1'
        # Query the historian
        topic_dict = fake_agent.vip.rpc.call('platform.historian',
                                             'get_topics_by_pattern',
                                             topic_pattern=pattern_1).get(timeout=100)
        print('Query Result', topic_dict)
        assert len(topic_dict) == 1
        expected = {"Building/LAB/Device/topic_matchme_1"}
        print(f"Set is expected {set(expected)} {topic_dict}")
        assert expected == set(topic_dict)

    def test_get_topics_by_pattern_failure(self, historian, fake_agent):
        """
        Test the get_topics_by_pattern api with invalid input(None).
        Expected result: RemoteError

        :param fake_agent: instance of fake volttron agent used to query
        using rpc
        :param historian: instance of the historian tested
        """
        global query_points, DEVICES_ALL_TOPIC, MICROSECOND_PRECISION
        identity, MICROSECOND_PRECISION = historian

        # Publish fake data. The format mimics the format used by VOLTTRON drivers.
        # Make some random readings
        oat_reading = self.random_uniform(30, 100)
        mixed_reading = oat_reading + self.random_uniform(-5, 5)

        all_message = [{'topic_matchme_1': oat_reading,
                        'topic_matchme_2': mixed_reading},
                       {'topic_matchme_1': float_meta,
                        'topic_matchme_2': float_meta}]

        # Create timestamp
        now = format_timestamp(datetime.now(timezone.utc))

        # now = '2015-12-02T00:00:00'
        headers = {
            headers_mod.DATE: now,
            headers_mod.TIMESTAMP: now
        }
        print("Published time in header: " + now)
        # Publish messages
        fake_agent.vip.pubsub.publish('pubsub', DEVICES_ALL_TOPIC, headers, all_message)

        gevent.sleep(2)

        pattern_1 = None
        # Query the historian
        # Should return empty or throw RemoteError due to None
        try:
            return_value = fake_agent.vip.rpc.call('platform.historian',
                                    'get_topics_by_pattern',
                                    topic_pattern=pattern_1).get(timeout=10)
            # postgresql historian handles none and return empty result
            assert not return_value
        except RemoteError as e:
            # SQLiteHistorian through None type exception
            print(f"Exception {e}")


    def test_get_version(self, historian, fake_agent):
        """
        Test the get_version api
        Expected result: Not null value

        :param fake_agent: instance of fake volttron agent used to query
        using rpc
        :param historian: instance of the historian tested
        """
        global query_points, DEVICES_ALL_TOPIC, MICROSECOND_PRECISION
        identity, MICROSECOND_PRECISION = historian
        version = fake_agent.vip.rpc.call('platform.historian', 'get_version').get(timeout=10)
        assert version

    def test_insert(self, historian, fake_agent):
        """
        Test the insert api with valid input

        :param fake_agent: instance of fake volttron agent used to query
        using rpc
        :param historian: instance of the historian tested
        """
        global query_points, DEVICES_ALL_TOPIC, MICROSECOND_PRECISION
        identity, MICROSECOND_PRECISION = historian

        # Create a message for all points.
        all_message = [{'test1': 0.03,
                        'test2': 0.5,
                        'test3': 0.2},
                       {'test1': float_meta,
                        'test2': float_meta,
                        'test3': percent_meta
                        }]

        # Create timestamp
        now = format_timestamp(datetime.now(timezone.utc))

        # now = '2015-12-02T00:00:00'
        headers = {
            headers_mod.DATE: now,
            headers_mod.TIMESTAMP: now
        }

        to_send = [{'topic': DEVICES_ALL_TOPIC,
                    'headers': headers,
                    'message': all_message}]

        fake_agent.vip.rpc.call('platform.historian', 'insert', to_send).get(timeout=10)
        gevent.sleep(0.5)
        result = fake_agent.vip.rpc.call(identity, 'query', topic="Building/LAB/Device/test1").get(timeout=10)
        print(result)

    def test_insert_failure(self, historian, fake_agent):
        """
        Test the insert api with invalid input
        Expected result: RemoteError

        :param fake_agent: instance of fake volttron agent used to query
        using rpc
        :param historian: instance of the historian tested
        """
        global query_points, DEVICES_ALL_TOPIC, MICROSECOND_PRECISION
        identity, MICROSECOND_PRECISION = historian

        to_send = [{'topic': DEVICES_ALL_TOPIC,
                    'headers': None,
                    'message': None}]

        with pytest.raises(RemoteError):
            fake_agent.vip.rpc.call('platform.historian', 'insert', to_send).get(timeout=10)

    def test_get_topics_metadata(self, historian, fake_agent):
        """
        Test the get_topics_metadata api with valid inputs
        Expected result:
        Should be able to query data based on topic name. Result should contain
        both topic and corresponding metadata
        
        :param fake_agent: instance of fake volttron 3.0 agent used to query
        using rpc
        :param historian: instance of the historian tested
        """

        global query_points, DEVICES_ALL_TOPIC, MICROSECOND_PRECISION
        identity, MICROSECOND_PRECISION = historian

        # Create a message for all points.
        message = {'temp1': {'Readings': ['2015-12-02T00:00:00',
                                          2],
                             'Units': 'F',
                             'tz': 'UTC',
                             'data_type': 'int'},
                   'temp2': {'Readings': ['2015-12-02T00:00:00',
                                          0.45],
                             'Units': 'F',
                             'tz': 'UTC',
                             'data_type': 'double'},
                   }

        # Create timestamp
        now = format_timestamp(datetime.now(timezone.utc))
        print("now is ", now)
        headers = {
            headers_mod.DATE: now,
            headers_mod.TIMESTAMP: now
        }
        # Publish messages
        fake_agent.vip.pubsub.publish('pubsub', "datalogger/Building/LAB/Device", headers, message)
        gevent.sleep(3)

        # Query the historian
        result = fake_agent.vip.rpc.call(
            identity,
            'get_topics_metadata',
            topics="datalogger/Building/LAB/Device/temp1"
        ).get(timeout=10)

        print('Result', result)
        assert result['datalogger/Building/LAB/Device/temp1'] == \
               {'units': 'F', 'tz': 'UTC', 'type': 'int'}

        result = fake_agent.vip.rpc.call(
            identity,
            'get_topics_metadata',
            topics=["datalogger/Building/LAB/Device/temp1",
                    "datalogger/Building/LAB/Device/temp2"]
        ).get(timeout=10)

        print('Result', result)
        assert result['datalogger/Building/LAB/Device/temp1'] == \
               {'units': 'F', 'tz': 'UTC', 'type': 'int'}
        assert result['datalogger/Building/LAB/Device/temp2'] == \
               {'units': 'F', 'tz': 'UTC', 'type': 'float'}

    def test_get_topics_metadata_failure(self, historian, fake_agent):
        """
        Test the get_topics_metadata api with invalid input
        Expected result: RemoteError
        :param fake_agent: instance of fake volttron 3.0 agent used to query
        using rpc
        :param historian: instance of the historian tested
        """

        global query_points, DEVICES_ALL_TOPIC, MICROSECOND_PRECISION
        identity, MICROSECOND_PRECISION = historian
        errmsg = r"Please provide a valid topic name string or a list of topic names. Invalid input 1"
        with pytest.raises(RemoteError, match=errmsg):
            result = fake_agent.vip.rpc.call(
                identity,
                'get_topics_metadata',
                topics=1
            ).get(timeout=10)
