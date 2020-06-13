# -*- coding: utf-8 -*-
"""
description: MySQL Environment
"""

import re
import os
import time
import math
import datetime
import json
import threading
import MySQLdb
import numpy as np
import configs
import utils
import knobs
import requests
import psutil

TEMP_FILES = "/data/cdbtune/AutoTuner/train_result/tmp/"
BEST_NOW = "/data/cdbtune/AutoTuner/tuner/"
PROJECT_DIR = "/data/cdbtune/"
# TEMP_FILES = "/home/rmw/train_result/tmp/"
# PROJECT_DIR = "/home/rmw/"


class Status(object):
    OK = 'OK'
    FAIL = 'FAIL'
    RETRY = 'RETRY'


class MySQLEnv(object):

    def __init__(self, wk_type='read', method='sysbench', num_other_knobs=0, num_metric=63, alpha=1.0, beta1=0.5, beta2=0.5, time_decay1=1.0, time_decay2=1.0):

        self.db_info = None
        self.wk_type = wk_type
        self.score = 0.0
        self.steps = 0
        self.terminate = False
        self.last_external_metrics = None
        self.default_externam_metrics = None

        self.method = method
        self.alpha = alpha
        self.beta1 = beta1
        self.beta2 = beta2
        self.time_decay_1 = time_decay1
        self.time_decay_2 = time_decay2
        self.num_other_knobs = num_other_knobs
        self.num_metric = num_metric

    @staticmethod
    def _get_external_metrics(path, method='sysbench'):

        def parse_tpcc(file_path):
            with open(file_path) as f:
                lines = f.read()
            temporal_pattern = re.compile(".*?trx: (\d+.\d+), 95%: (\d+.\d+), 99%: (\d+.\d+), max_rt:.*?")
            temporal = temporal_pattern.findall(lines)
            tps = 0
            latency = 0
            qps = 0

            for i in temporal[-10:]:
                tps += float(i[0])
                latency += float(i[2])
            num_samples = len(temporal[-10:])
            tps /= num_samples
            latency /= num_samples
            # interval
            tps /= 1
            return [tps, latency, tps]

        def parse_sysbench(file_path):
            with open(file_path) as f:
                lines = f.read()
            temporal_pattern = re.compile(
                "tps: (\d+.\d+) qps: (\d+.\d+) \(r/w/o: (\d+.\d+)/(\d+.\d+)/(\d+.\d+)\)" 
                " lat \(ms,95%\): (\d+.\d+) err/s: (\d+.\d+) reconn/s: (\d+.\d+)")
            temporal = temporal_pattern.findall(lines)
            tps = 0
            latency = 0
            qps = 0

            for i in temporal[-10:]:
                tps += float(i[0])
                latency += float(i[5])
                qps += float(i[1])
            num_samples = len(temporal[-10:])
            tps /= num_samples
            qps /= num_samples
            latency /= num_samples
            return [tps, latency, qps]

        if method == 'sysbench':
            result = parse_sysbench(path)
        elif method == 'tpcc':
            result = parse_tpcc(path)
        else:
            result = parse_sysbench(path)
        return result

    def _get_internal_metrics(self, internal_metrics):
        """
        Args:
            internal_metrics: list,
        Return:

        """
        _counter = 0
        _period = 5
        count = 160/5

        def collect_metric(counter):
            counter += 1
            timer = threading.Timer(_period, collect_metric, (counter,))
            timer.start()
            if counter >= count:
                timer.cancel()
            try:
                data = utils.get_metrics(self.db_info)
                internal_metrics.append(data)
            except Exception as err:
                print "[GET Metrics]Exception:" ,err

        collect_metric(_counter)

        return internal_metrics

    def _post_handle(self, metrics):
        result = np.zeros(self.num_metric)

        def do(metric_name, metric_values):
            metric_type = utils.get_metric_type(metric_name)
            if metric_type == 'counter':
                return float(metric_values[-1] - metric_values[0])
            else:
                return float(sum(metric_values))/len(metric_values)

        keys = metrics[0].keys()

        keys.sort()
        for idx in xrange(len(keys)):
            key = keys[idx]
            data = [x[key] for x in metrics]
            result[idx] = do(key, data)
        return result

    def initialize(self):
        """Initialize the mysql instance environment
        """
        pass

    def eval(self, knob):
        """ Evaluate the knobs
        Args:
            knob: dict, mysql parameters
        Returns:
            result: {tps, latency}
        """
        flag = self._apply_knobs(knob)
        if not flag:
            return {"tps": 0, "latency": 0}

        external_metrics, _ = self._get_state(knob, method=self.method)
        return {"tps": external_metrics[0],
                "latency": external_metrics[1]}
    def _get_best_now(self, filename):
        with open(BEST_NOW  + filename) as f:
            lines = f.readlines()
        best_now = lines[0].split(',')
        return [float(best_now[0]), float(best_now[1]), float(best_now[0])]

    def record_best(self, external_metrics):
        filename = 'bestnow.log'
        best_flag = False
        if os.path.exists( BEST_NOW  + filename):
            tps_best = external_metrics[0]
            lat_best = external_metrics[1]
            rate = 0
            if int(lat_best) != 0:
                rate = float(tps_best)/lat_best
                with open(BEST_NOW  + filename) as f:
                    lines = f.readlines()
                best_now = lines[0].split(',')
                rate_best_now = float(best_now[0])/float(best_now[1])
                if rate > rate_best_now:
                    best_flag = True
                    with open(BEST_NOW  + filename, 'w') as f:
                        f.write(str(tps_best) + ',' + str(lat_best) + ',' + str(rate))
        else:
            file = open(BEST_NOW  + filename, 'wr')
            tps_best = external_metrics[0]
            lat_best = external_metrics[1]
            rate = 0
            if int(lat_best) == 0 :
                rate = 0
            else:
                rate = float(tps_best)/lat_best
            file.write(str(tps_best) + ',' + str(lat_best) + ',' + str(rate))
        return best_flag

    def step(self, knob):
        """step
        """
        filename = 'bestnow.log'
        restart_time = utils.time_start()
        flag = self._apply_knobs(knob)
        restart_time = utils.time_end(restart_time)
        if not flag:
            return -10000000.0, np.array([0] * self.num_metric), True, self.score - 10000000, [0, 0, 0], restart_time
        s = self._get_state(knob, method=self.method)
        if s is None:
            return -10000000.0, np.array([0] * self.num_metric), True, self.score - 10000000, [0, 0, 0], restart_time
        external_metrics, internal_metrics = s

        reward = self._get_reward(external_metrics)
        flag = self.record_best(external_metrics)
        if flag == True:
            print('Better performance changed!')
        else:
            print('Performance remained!')
        #get the best performance so far to calculate the reward
        best_now_performance = self._get_best_now(filename)
        self.last_external_metrics = best_now_performance

        next_state = internal_metrics
        terminate = self._terminate()
        knobs.save_knobs(
            knob=knob,
            metrics=external_metrics,
            knob_file='%sAutoTuner/tuner/save_knobs/knob_metric.txt' % PROJECT_DIR
        )
        return reward, next_state, terminate, self.score, external_metrics, restart_time

    def setting(self, knob):
        self._apply_knobs(knob)
    
    def _get_state(self, knob, method='sysbench'):
        """Collect the Internal State and External State
        """
        filename = TEMP_FILES
        if not os.path.exists(filename):
            os.mkdir(filename)
        timestamp = int(time.time())
        filename += '%s.txt' % timestamp
        internal_metrics = []
        self._get_internal_metrics(internal_metrics)
        #calculate the sysbench time automaticly
        if knob['innodb_buffer_pool_size'] < 161061273600:
            time_sysbench = 150
        else:
            time_sysbench = int(knob['innodb_buffer_pool_size']/1024.0/1024.0/1024.0/1.1)
        if method == 'sysbench':
            a = time.time()
            print "bash %sAutoTuner/scripts/run_sysbench.sh %s %s %d %s %d %s" % (PROJECT_DIR,
                                                                                   self.wk_type,
                                                                                   self.db_info['host'],
                                                                                   self.db_info['port'],
                                                                                   self.db_info['passwd'],
                                                                                   time_sysbench,
                                                                                   filename)
            os.system("bash %sAutoTuner/scripts/run_sysbench.sh %s %s %d %s %d %s" % (PROJECT_DIR,
                                                                                   self.wk_type,
                                                                                   self.db_info['host'],
                                                                                   self.db_info['port'],
                                                                                   self.db_info['passwd'],
                                                                                   time_sysbench,
                                                                                   filename))
            a = time.time() - a
            if a < 50:
                return None
            time.sleep(10)
        elif method == 'tpcc':
            def kill_tpcc():
                def _filter_pid(x):
                    try:
                        x = psutil.Process(x)
                        if x.name() == 'tpcc_start':
                            return True
                        return False
                    except:
                        return False
                pids = psutil.pids()
                tpcc_pid = filter(_filter_pid, pids)
                print tpcc_pid
                for tpcc_pid_i in tpcc_pid:
                    os.system('kill %s' % tpcc_pid_i)

            timer = threading.Timer(170, kill_tpcc)
            timer.start()
            os.system('bash %sAutoTuner/scripts/run_tpcc.sh %s %d %s %s' % (PROJECT_DIR,
                                                                            self.db_info['host'],
                                                                            self.db_info['port'],
                                                                            self.db_info['passwd'],
                                                                            filename))
            time.sleep(10)

        external_metrics = self._get_external_metrics(filename, method)
        internal_metrics = self._post_handle(internal_metrics)

        return external_metrics, internal_metrics

    def _apply_knobs(self, knob):
        """ Apply Knobs to the instance
        """
        pass

    @staticmethod
    def _calculate_reward(delta0, deltat):

        if delta0 > 0:
            _reward = ((1+delta0)**2-1) * math.fabs(1+deltat)
        else:
            _reward = - ((1-delta0)**2-1) * math.fabs(1-deltat)

        if _reward > 0 and deltat < 0:
            _reward = 0
        return _reward

    def _get_reward(self, external_metrics):
        """
        Args:
            external_metrics: list, external metric info, including `tps` and `qps`
        Return:
            reward: float, a scalar reward
        """
        print('*****************************')
        print(external_metrics)
        print(self.default_externam_metrics)
        print(self.last_external_metrics)
        print('*****************************')
        # tps
        delta_0_tps = float((external_metrics[0] - self.default_externam_metrics[0]))/self.default_externam_metrics[0]
        delta_t_tps = float((external_metrics[0] - self.last_external_metrics[0]))/self.last_external_metrics[0]

        tps_reward = self._calculate_reward(delta_0_tps, delta_t_tps)

        # latency
        delta_0_lat = float((-external_metrics[1] + self.default_externam_metrics[1])) / self.default_externam_metrics[1]
        delta_t_lat = float((-external_metrics[1] + self.last_external_metrics[1])) / self.last_external_metrics[1]

        lat_reward = self._calculate_reward(delta_0_lat, delta_t_lat)
        
        reward = tps_reward * 0.4 + 0.6 * lat_reward
        self.score += reward
        print('$$$$$$$$$$$$$$$$$$$$$$')
        print(tps_reward)
        print(lat_reward)
        print(reward)
        print('$$$$$$$$$$$$$$$$$$$$$$')
        if reward > 0:
            reward = reward*1000000
        return reward

    def _terminate(self):
        return self.terminate


class Server(MySQLEnv):
    """ Build an environment directly on Server
    """

    def __init__(self, wk_type, instance_name):
        MySQLEnv.__init__(self, wk_type)
        self.wk_type = wk_type
        self.score = 0.0
        self.steps = 0
        self.terminate = False
        self.last_external_metrics = None
        self.instance_name = instance_name
        self.db_info = configs.instance_config[instance_name]
        self.server_ip = self.db_info['host']
        self.alpha = 1.0
        knobs.init_knobs(instance_name, num_more_knobs=0)
        self.default_knobs = knobs.get_init_knobs()

    def initialize(self):
        """ Initialize the environment when an episode starts
        Returns:
            state: np.array, current state
        """
        self.score = 0.0
        self.last_external_metrics = []
        self.steps = 0
        self.terminate = False

        flag = self._apply_knobs(self.default_knobs)
        i = 0
        while not flag:
            flag = self._apply_knobs(self.default_knobs)
            i += 1
            if i >= 5:
                print("Initialize: {} times ....".format(i))

        external_metrics, internal_metrics = self._get_state(knob = self.default_knobs, method=self.method)
        self.last_external_metrics = external_metrics
        self.default_externam_metrics = external_metrics
        state = internal_metrics
        knobs.save_knobs(
            self.default_knobs,
            metrics=external_metrics,
            knob_file='%sAutoTuner/tuner/save_knobs/knob_metric.txt' % PROJECT_DIR
        )
        return state, external_metrics

    def _apply_knobs(self, knob):
        """ Apply the knobs to the mysql
        Args:
            knob: dict, mysql parameters
        Returns:
            flag: whether the setup is valid
        """
        self.steps += 1
        utils.modify_configurations(
            server_ip=self.server_ip,
            instance_name=self.instance_name,
            configuration=knob
        )

        steps = 0
        max_steps = 300
        flag = utils.test_mysql(self.instance_name)
        while not flag and steps < max_steps:
            _st = utils.get_mysql_state(self.server_ip)
            time.sleep(5)
            flag = utils.test_mysql(self.instance_name)
            steps += 1

        if not flag:
            utils.modify_configurations(
                server_ip=self.server_ip,
                instance_name=self.instance_name,
                configuration=self.default_knobs
            )
            params = ''
            for key in knob.keys():
                params += ' --%s=%s' % (key, knob[key])
            with open('failed.log', 'a+') as f:
                f.write('{}\n'.format(params))
            return False
        else:
            return True


DockerServer = Server