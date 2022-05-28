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

        self.sensorDevices = {}  # Indigo device IDs, keyed by address (sensor ID)

        self.updateFrequency = float(pluginPrefs.get('updateFrequency', "1")) * 60.0
        self.logger.debug(f"updateFrequency = {self.updateFrequency}")
        self.next_update = time.time()

        self.apiReadKey = pluginPrefs.get("apiReadKey", None)
        self.api_key_ok = self.read_key_ok(self.apiReadKey)

    def read_key_ok(self, key) -> bool:
        self.apiReadKey = key
        if not (self.apiReadKey and len(self.apiReadKey)):
            self.logger.error("API Read Key must be specified in Plugin Config")
            return False

        try:
            response = requests.get(f"https://api.purpleair.com/v1/keys", headers={'X-API-Key': self.apiReadKey})
        except requests.exceptions.RequestException as err:
            self.logger.error(f"{device.name}: check key RequestException: {err}")
            return False

        try:
            if response.json()['api_key_type'] != "READ":
                self.logger.error("Invalid API Read Key specified in Plugin Config")
                return False
        except (Exception,):
            self.logger.error("Invalid API Key request response")
            return False

        return True

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
            try:
                response = requests.get(f"https://api.purpleair.com/v1/sensors/{sensorID}", headers={'X-API-Key': self.apiReadKey})
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
                    {'key': 'temperature',  'value': sensor_data['temperature'], 'decimalPlaces': 0},
                    {'key': 'humidity',     'value': sensor_data['humidity'],    'decimalPlaces': 0},
                    {'key': 'pressure',     'value': sensor_data['pressure'],    'decimalPlaces': 2},
                    {'key': 'model',        'value': sensor_data['model']},
                    {'key': 'latitude',     'value': sensor_data['latitude']},
                    {'key': 'longitude',    'value': sensor_data['longitude']},
                    {'key': 'altitude',     'value': sensor_data['altitude']},
                    {'key': 'rssi',         'value': sensor_data['rssi']},
                    {'key': 'uptime',       'value': sensor_data['uptime']},
                    {'key': 'version',      'value': sensor_data['firmware_version']},
                    {'key': 'hardware',     'value': sensor_data['hardware']},
                    {'key': 'last_seen',    'value': time.strftime("%a, %d %b %Y %H:%M:%S",time.localtime(sensor_data['last_seen']))},
                    {'key': 'pm1_0',        'value': sensor_data['pm1.0']},
                    {'key': 'pm2_5',        'value': sensor_data['pm2.5']},
                    {'key': 'pm10_0',       'value': sensor_data['pm10.0']},

                ]
                device.updateStatesOnServer(state_list)

    ########################################
    # PluginConfig methods
    ########################################
    def validatePrefsConfigUi(self, valuesDict):
        errorDict = indigo.Dict()
        updateFrequency = int(valuesDict.get('updateFrequency', 15))
        if (updateFrequency < 5) or (updateFrequency > 60):
            errorDict['updateFrequency'] = "Update frequency is invalid - enter a valid number (between 5 and 60)"

        if not self.read_key_ok(valuesDict.get("apiReadKey", None)):
            errorDict['apiReadKey'] = "Invalid API Read Key"

        if len(errorDict) > 0:
            return False, valuesDict, errorDict
        return True

    def closedPrefsConfigUi(self, valuesDict, userCancelled):
        if not userCancelled:
            self.logLevel = int(valuesDict.get("logLevel", logging.INFO))
            self.indigo_log_handler.setLevel(self.logLevel)
            self.logger.debug(f"logLevel = {self.logLevel}")
            self.updateFrequency = float(valuesDict.get('updateFrequency', "1")) * 60.0
            self.apiReadKey = valuesDict.get("apiReadKey", None)
            self.api_key_ok = self.read_key_ok(self.apiReadKey)
