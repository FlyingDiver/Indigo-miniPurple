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

        try:
            self.logLevel = int(self.pluginPrefs[u"logLevel"])
        except:
            self.logLevel = logging.INFO
        self.indigo_log_handler.setLevel(self.logLevel)
    

    def startup(self):
        indigo.server.log(u"Starting miniPurple")

        self.sensorDevices = {}     # Indigo device IDs, keyed by address (sensor ID)
        
        self.updateFrequency = float(self.pluginPrefs.get('updateFrequency', "1")) * 60.0
        self.logger.debug(u"updateFrequency = {}".format(self.updateFrequency))
        self.next_update = time.time()


    def shutdown(self):
        indigo.server.log(u"Shutting down miniPurple")


    def runConcurrentThread(self):
        self.logger.debug(u"Starting runConcurrentThread")

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
            self.logger.debug(u"{}: deviceStartComm: Adding device ({}) to sensor list".format(device.name, device.id))
            assert device.address not in self.sensorDevices
            self.sensorDevices[device.address] = device.id
            self.logger.threaddebug(u"devices = {}".format(self.sensorDevices))
            
        
    def deviceStopComm(self, device):

        if device.deviceTypeId == 'purpleSensor':
            self.logger.debug(u"{}: deviceStopComm: Removing device ({}) from device list".format(device.name, device.id))
            assert device.address in self.sensorDevices
            del self.sensorDevices[device.address]


    def getData(self):

        for sensorID, devID in self.sensorDevices.iteritems():

            device = indigo.devices[devID]

            url = "https://www.purpleair.com/json?show={}".format(sensorID)
            try:
                response = requests.get(url)
            except requests.exceptions.RequestException as err:
                self.logger.error(u"{}: getData RequestException: {}".format(device.name, err))
            else:
                self.logger.threaddebug(u"{}: getData for sensor {}:\n{}".format(device.name, sensorID, response.text))
                try:
                    sensorData = response.json()['results'][0]
                except:
                    self.logger.error(u"{}: getData 'results' key missing: {}".format(device.name, response.text))
                    return

                try:
                    sensorStats = json.loads(sensorData['Stats'])
                except:
                    self.logger.error(u"{}: getData 'Stats' key missing: {}".format(device.name, response.text))
                    return

                sensor_aqi = int(aqi.to_iaqi(aqi.POLLUTANT_PM25, sensorData['PM2_5Value'], algo=aqi.ALGO_EPA))
                state_list = [
                    {'key': 'sensorValue',  'value': sensor_aqi,               'uiValue': "{}".format(sensor_aqi)},
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
            try:
                self.logLevel = int(valuesDict[u"logLevel"])
            except:
                self.logLevel = logging.INFO
            self.indigo_log_handler.setLevel(self.logLevel)

            try:
                self.updateFrequency = float(valuesDict[u"updateFrequency"]) * 60.0
            except:
                self.updateFrequency = 60.0


