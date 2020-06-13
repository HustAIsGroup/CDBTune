# -*- coding: utf-8 -*-
"""
description: Evaluate the Model
"""

import os
import sys
import utils
import pickle
import argparse
sys.path.append('../')
import models
import environment
import numpy as np


parser = argparse.ArgumentParser()
parser.add_argument('--tencent', action='store_true', help='Use Tencent Server')
parser.add_argument('--params', type=str, required=True, help='Load existing parameters')
parser.add_argument('--workload', type=str, default='read', help='Workload type [`read`, `write`, `readwrite`]')
parser.add_argument('--instance', type=str, default='mysql1', help='Choose MySQL Instance')
parser.add_argument('--method', type=str, default='ddpg', help='Choose Algorithm to solve [`ddpg`,`dqn`]')
parser.add_argument('--memory', type=str, default='', help='add replay memory')
parser.add_argument('--max_steps', type=int, default=50, help='evaluate test steps')
parser.add_argument('--other_knob', type=int, default=0, help='Number of other knobs')
parser.add_argument('--batch_size', type=int, default=2, help='Training Batch Size')
parser.add_argument('--benchmark', type=str, default='sysbench', help='[sysbench, tpcc]')
parser.add_argument('--metric_num', type=int, default=65, help='metric nums')

opt = parser.parse_args()

# Create Environment
if opt.tencent:
    env = environment.TencentServer(
        wk_type=opt.workload,
        instance_name=opt.instance,
        method=opt.benchmark,
        num_metric=opt.metric_num,
        num_other_knobs=opt.other_knob)
else:
    env = environment.Server(wk_type=opt.workload, instance_name=opt.instance)

# Build models
ddpg_opt = dict()
ddpg_opt['tau'] = 0.00001
ddpg_opt['alr'] = 0.00001
ddpg_opt['clr'] = 0.00001
ddpg_opt['model'] = opt.params

n_states = opt.metric_num
gamma = 0.9
memory_size = 100000
num_actions = 16 + opt.other_knob
ddpg_opt['gamma'] = gamma
ddpg_opt['batch_size'] = opt.batch_size
ddpg_opt['memory_size'] = memory_size

model = models.DDPG(
    n_states=n_states,
    n_actions=num_actions,
    opt=ddpg_opt,
    ouprocess=True
)

if not os.path.exists('log'):
    os.mkdir('log')

if not os.path.exists('test_knob'):
    os.mkdir('test_knob')

expr_name = 'eval_{}_{}'.format(opt.method, str(utils.get_timestamp()))

logger = utils.Logger(
    name=opt.method,
    log_file='log/{}.log'.format(expr_name)
)

if opt.other_knob != 0:
    logger.warn('USE Other Knobs')

# Load mean value and varianc

current_knob = environment.get_init_knobs()


def compute_percentage(default, current):
    """ compute metrics percentage versus default settings
    Args:
        default: dict, metrics from default settings
        current: dict, metrics from current settings
    """
    delta_tps = 100*(current[0] - default[0]) / default[0]
    delta_latency = 100*(-current[1] + default[1]) / default[1]
    return delta_tps, delta_latency


def generate_knob(action, method):
    if method == 'ddpg':
        return environment.gen_continuous(action)
    else:
        raise NotImplementedError()


if len(opt.memory) > 0:
    model.replay_memory.load_memory(opt.memory)
    print("Load Memory: {}".format(len(model.replay_memory)))

step_counter = 0
train_step = 0
if opt.method == 'ddpg':
    accumulate_loss = [0, 0]
else:
    accumulate_loss = 0

max_score = 0
max_idx = -1
generate_knobs = []
current_state, default_metrics = env.initialize()
model.reset(0.1)

# time for every step
step_times = []
# time for training
train_step_times = []
# time for setup, restart, test
env_step_times = []
# restart time
env_restart_times = []
# choose_action_time
action_step_times = []

print("[Environment Intialize]Tps: {} Lat:{}".format(default_metrics[0], default_metrics[1]))
print("------------------- Starting to Test -----------------------")
while step_counter < opt.max_steps:
    step_time = utils.time_start()

    state = current_state

    action_step_time = utils.time_start()
    action = model.choose_action(state)
    action_step_time = utils.time_end(action_step_time)

    current_knob = generate_knob(action, 'ddpg')
    logger.info("[ddpg] Action: {}".format(action))

    env_step_time = utils.time_start()
    reward, state_, done, score, metrics, restart_time = env.step(current_knob)
    env_step_time = utils.time_end(env_step_time)

    logger.info("[{}][Step: {}][Metric tps:{} lat:{}, qps: {}]Reward: {} Score: {} Done: {}".format(
        opt.method, step_counter, metrics[0], metrics[1], metrics[2], reward, score, done
    ))

    _tps, _lat = compute_percentage(default_metrics, metrics)

    logger.info("[{}][Knob Idx: {}] tps increase: {}% lat decrease: {}%".format(
        opt .method, step_counter, _tps, _lat
    ))

    if _tps + _lat > max_score:
        max_score = _tps + _lat
        max_idx = step_counter

    next_state = state_
    model.add_sample(state, action, reward, next_state, done)

    # {"tps_inc":xxx, "lat_dec": xxx, "metrics": xxx, "knob": xxx}
    generate_knobs.append({"tps_inc": _tps, "lat_dec": _lat, "metrics": metrics, "knob": current_knob})

    with open('test_knob/'+expr_name + '.pkl', 'wb') as f:
        pickle.dump(generate_knobs, f)

    current_state = next_state
    train_step_time = 0.0
    if len(model.replay_memory) >= opt.batch_size:
        losses = []
        train_step_time = utils.time_start()
        for i in xrange(2):
            losses.append(model.update())
            train_step += 1
        train_step_time = utils.time_end(train_step_time) / 2.0

        accumulate_loss[0] += sum([x[0] for x in losses])
        accumulate_loss[1] += sum([x[1] for x in losses])
        logger.info('[{}][Step: {}] Critic: {} Actor: {}'.format(
            opt.method, step_counter, accumulate_loss[0] / train_step, accumulate_loss[1] / train_step
        ))

    # all_step time
    step_time = utils.time_end(step_time)
    step_times.append(step_time)
    # env_step_time
    env_step_times.append(env_step_time)
    # training step time
    train_step_times.append(train_step_time)
    # action step times
    action_step_times.append(action_step_time)

    logger.info("[{}][Step: {}] step: {}s env step: {}s train step: {}s restart time: {}s "
                "action time: {}s"
                .format(opt.method, step_counter, step_time, env_step_time, train_step_time, restart_time,
                        action_step_time))

    logger.info("[{}][Step: {}][Average] step: {}s env step: {}s train step: {}s "
                "restart time: {}s action time: {}s"
                .format(opt.method, step_counter, np.mean(step_time), np.mean(env_step_time),
                        np.mean(train_step_time), np.mean(restart_time), np.mean(action_step_times)))

    step_counter += 1

    if done:
        current_state, _ = env.initialize()
        model.reset(0.01)

print("------------------- Testing Finished -----------------------")

print("Knobs are saved at: {}".format('test_knob/'+expr_name + '.pkl'))
print("Proposal Knob At {}".format(max_idx))

