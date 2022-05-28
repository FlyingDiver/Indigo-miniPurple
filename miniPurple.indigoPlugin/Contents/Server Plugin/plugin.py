#! /usr/bin/env python
# -*- coding: utf-8 -*-
####################

import time
import requests
import logging
import json
import aqi

################################################################################
class Plugin(indigo.PluginBase):

    ########################################
    # Main Plugin methods
    ########################################
    def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
        indigo.PluginBase.__init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs)

        pfmt = logging.Formatter('%(asctime)s.%(msecs)03d\t[%(levelname)8s] %(name)20s.%(funcName)-25s%(msg)s', datefmt='%Y-%m-%d %H:%M:%S')
        self.plugin_file_handler.setFormatter(pfmt)
        self.logLevel = int(pluginPrefs.get("logLevel", logging.INFO))
        self.indigo_log_handler.setLevel(self.logLevel)
        self.logger.debug(f"logLevel = {self.logLevel}")
        self.api_key_ok = False

        self.sensorDevices = {}  # Indigo device IDs, keyed by address (sensor ID)

        self.apiReadKey = pluginPrefs.get("apiReadKey", None)
        if not (self.apiReadKey and len(self.apiReadKey)):
            self.logger.error("API Read Key must be specified in Plugin Config")
        else:
            url = f"https://api.purpleair.com/v1/keys"
            my_headers = {'X-API-Key': self.apiReadKey}
            try:
                response = requests.get(url, headers=my_headers)
            except requests.exceptions.RequestException as err:
                self.logger.error(f"{device.name}: check key RequestException: {err}")
            else:
                if response.json()['api_key_type'] != "READ":
                    self.logger.error("Invalid API Read Key specified in Plugin Config")
                else:
                    self.api_key_ok = True

        self.updateFrequency = float(pluginPrefs.get('updateFrequency', "1")) * 60.0
        self.logger.debug(f"updateFrequency = {self.updateFrequency}")
        self.next_update = time.time()

    def startup(self):
        self.logger.info("Starting miniPurple")

    def shutdown(self):
        self.logger.info("Stopping miniPurple")

    def runConcurrentThread(self):
        try:
            while True:
                if time.time() > self.next_update:
                    if self.api_key_ok:
                        self.getData()
                    self.next_update = time.time() + self.updateFrequency
                self.sleep(1.0)
        except self.StopThread:
            pass

    def deviceStartComm(self, device):
            
        if device.deviceTypeId == 'purpleSensor':
            self.logger.debug(f"{device.name}: deviceStartComm: Adding device ({device.id}) to sensor list")
            assert device.address not in self.sensorDevices
            self.sensorDevices[device.address] = device.id
            self.logger.threaddebug(f"devices = {self.sensorDevices}")

        device.stateListOrDisplayStateIdChanged()

    def deviceStopComm(self, device):

        if device.deviceTypeId == 'purpleSensor':
            self.logger.debug(f"{device.name}: deviceStopComm: Removing device ({device.id}) from device list")
            assert device.address in self.sensorDevices
            del self.sensorDevices[device.address]

    def getData(self):

        for sensorID, devID in self.sensorDevices.items():

            device = indigo.devices[devID]

            url = f"https://api.purpleair.com/v1/sensors/{sensorID}"
            my_headers = {'X-API-Key': self.apiReadKey}
            try:
                response = requests.get(url, headers=my_headers)
            except requests.exceptions.RequestException as err:
                self.logger.error(f"{device.name}: getData RequestException: {err}")
            else:
                self.logger.threaddebug(f"{device.name}: getData for sensor {sensorID}:\n{response.text}")
                try:
                    sensor_data = response.json()['sensor']
                except (Exception,):
                    self.logger.error(f"{device.name}: getData 'results' key missing: {response.text}")
                    return

                sensor_aqi = int(aqi.to_iaqi(aqi.POLLUTANT_PM25, sensor_data['pm2.5'], algo=aqi.ALGO_EPA))
                state_list = [
                    {'key': 'sensorValue',  'value': sensor_aqi, "uiValue": f"{sensor_aqi}"},
                    {'key': 'Temperature',  'value': sensor_data['temperature'], 'decimalPlaces': 0},
                    {'key': 'Humidity',     'value': sensor_data['humidity'],    'decimalPlaces': 0},
                    {'key': 'Pressure',     'value': sensor_data['pressure'],    'decimalPlaces': 2},
                    {'key': 'Name',         'value': sensor_data['name']},
                    {'key': 'Latitude',     'value': sensor_data['latitude']},
                    {'key': 'Longitude',    'value': sensor_data['longitude']},
                    {'key': 'Altitude',     'value': sensor_data['altitude']},
                    {'key': 'RSSI',         'value': sensor_data['rssi']},
                    {'key': 'Uptime',       'value': sensor_data['uptime']},
                    {'key': 'Version',      'value': sensor_data['firmware_version']},
                    {'key': 'Hardware',     'value': sensor_data['hardware']},
                    {'key': 'pm1_0',        'value': sensor_data['pm1.0']},
                    {'key': 'pm2_5',        'value': sensor_data['pm2.5']},
                    {'key': 'pm10_0',       'value': sensor_data['pm10.0']},

                ]
                device.updateStatesOnServer(state_list)

    ########################################
    # PluginConfig methods
    ########################################

    def closedPrefsConfigUi(self, valuesDict, userCancelled):
        if not userCancelled:
            self.logLevel = int(valuesDict.get("logLevel", logging.INFO))
            self.indigo_log_handler.setLevel(self.logLevel)
            self.logger.debug(f"logLevel = {self.logLevel}")
            self.updateFrequency = float(valuesDict.get('updateFrequency', "1")) * 60.0
