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
        self.logLevel = int(self.pluginPrefs,get("logLevel", logging.INFO))
        self.indigo_log_handler.setLevel(self.logLevel)

        self.sensorDevices = {}  # Indigo device IDs, keyed by address (sensor ID)

        self.updateFrequency = float(self.pluginPrefs.get('updateFrequency', "1")) * 60.0
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
        
    def deviceStopComm(self, device):

        if device.deviceTypeId == 'purpleSensor':
            self.logger.debug(f"{device.name}: deviceStopComm: Removing device ({device.id}) from device list")
            assert device.address in self.sensorDevices
            del self.sensorDevices[device.address]

    def getData(self):

        for sensorID, devID in self.sensorDevices.iteritems():

            device = indigo.devices[devID]

            url = f"https://www.purpleair.com/json?show={sensorID}"
            try:
                response = requests.get(url)
            except requests.exceptions.RequestException as err:
                self.logger.error(f"{device.name}: getData RequestException: {err}")
            else:
                self.logger.threaddebug(f"{device.name}: getData for sensor {sensorID}:\n{response.text}")
                try:
                    sensorData = response.json()['results'][0]
                except (Exception,):
                    self.logger.error(f"{device.name}: getData 'results' key missing: {response.text}")
                    return

                try:
                    sensorStats = json.loads(sensorData['Stats'])
                except (Exception,):
                    self.logger.error(f"{device.name}: getData 'Stats' key missing: {response.text}")
                    return

                sensor_aqi = int(aqi.to_iaqi(aqi.POLLUTANT_PM25, sensorData['PM2_5Value'], algo=aqi.ALGO_EPA))
                state_list = [
                    {'key': 'sensorValue',  'value': sensor_aqi,               'uiValue': f"{sensor_aqi}"},
                    {'key': 'Temperature',  'value': sensorData['temp_f'],     'decimalPlaces': 0},
                    {'key': 'Humidity',     'value': sensorData['humidity'],   'decimalPlaces': 0},
                    {'key': 'Pressure',     'value': sensorData['pressure'],   'decimalPlaces': 2},
                    {'key': 'Label',        'value': sensorData['Label']},
                    {'key': 'Latitude',     'value': sensorData['Lat']},
                    {'key': 'Longitude',    'value': sensorData['Lon']},
                    {'key': 'RSSI',         'value': sensorData['RSSI']},
                    {'key': 'Uptime',       'value': sensorData['Uptime']},
                    {'key': 'Version',      'value': sensorData['Version']},
                    {'key': 'Hardware',     'value': sensorData['DEVICE_HARDWAREDISCOVERED']},
                    {'key': 'p_0_3_um',     'value': sensorData['p_0_3_um']},
                    {'key': 'p_0_5_um',     'value': sensorData['p_0_5_um']},
                    {'key': 'p_10_0_um',    'value': sensorData['p_10_0_um']},
                    {'key': 'p_1_0_um',     'value': sensorData['p_1_0_um']},
                    {'key': 'p_2_5_um',     'value': sensorData['p_2_5_um']},
                    {'key': 'p_5_0_um',     'value': sensorData['p_5_0_um']},
                    {'key': 'pm10_0_atm',   'value': sensorData['pm10_0_atm']},
                    {'key': 'pm10_0_cf_1',  'value': sensorData['pm10_0_cf_1']},
                    {'key': 'pm1_0_atm',    'value': sensorData['pm1_0_atm']},
                    {'key': 'pm1_0_cf_1',   'value': sensorData['pm1_0_cf_1']},
                    {'key': 'pm2_5_atm',    'value': sensorData['pm2_5_atm']},
                    {'key': 'pm2_5_cf_1',   'value': sensorData['pm2_5_cf_1']},

                    {'key': 'pm2_5_current','value': sensorStats['v']},
                    {'key': 'pm2_5_10m',    'value': sensorStats['v1']},
                    {'key': 'pm2_5_30m',    'value': sensorStats['v2']},
                    {'key': 'pm2_5_1h',     'value': sensorStats['v3']},
                    {'key': 'pm2_5_6h',     'value': sensorStats['v4']},
                    {'key': 'pm2_5_24h',    'value': sensorStats['v5']},
                    {'key': 'pm2_5_1w',     'value': sensorStats['v6']},
                    
                ]
                device.updateStatesOnServer(state_list)

    ########################################
    # PluginConfig methods
    ########################################

    def closedPrefsConfigUi(self, valuesDict, userCancelled):
        if not userCancelled:
            self.logLevel = int(valuesDict,get("logLevel", logging.INFO))
            self.indigo_log_handler.setLevel(self.logLevel)
            self.updateFrequency = float(valuesDict.get('updateFrequency', "1")) * 60.0
