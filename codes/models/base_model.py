import os
import random
import torch
import torch.nn as nn
import numpy as np
from collections import Counter


class BaseModel():
    def __init__(self, opt):
        self.opt = opt
        # self.device = torch.device('cuda' if opt['gpu_ids'] is not None else 'cpu')
        if opt['gpu_ids'] is not None:
            torch.cuda.current_device()
            torch.cuda.empty_cache()
            self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        else:
            self.device = 'cpu'
        
        self.is_train = opt['is_train']
        self.schedulers = []
        self.optimizers = []

    def feed_data(self, data):
        pass

    def optimize_parameters(self, step):
        pass

    def get_current_visuals(self):
        pass

    def get_current_losses(self):
        pass

    def print_network(self):
        pass

    def save(self, label):
        pass

    def load(self):
        pass

    def update_learning_rate(self):
        for scheduler in self.schedulers:
            scheduler.step()

    if torch.__version__ >= '1.4.0':
        def get_current_learning_rate(self):
            return self.schedulers[0].get_last_lr()[0]
    else:
        def get_current_learning_rate(self):
            return self.schedulers[0].get_lr()[0]

    def get_network_description(self, network):
        '''Get the string and total parameters of the network'''
        if isinstance(network, nn.DataParallel):
            network = network.module
        s = str(network)
        n = sum(map(lambda x: x.numel(), network.parameters()))
        return s, n

    def save_network(self, network, network_label, iter_step, name=None):
        if name:
            save_filename = '{}_{}_{}.pth'.format(name, iter_step, network_label)
        else:
            save_filename = '{}_{}.pth'.format(iter_step, network_label)
        save_path = os.path.join(self.opt['path']['models'], save_filename)
        if isinstance(network, nn.DataParallel):
            network = network.module
        state_dict = network.state_dict()
        for key, param in state_dict.items():
            state_dict[key] = param.cpu()
        if iter_step == 'backup':
            if os.path.exists(save_path):
                lbk_path = os.path.join(self.opt['path']['models'], 'backup-old_{}.pth'.format(network_label))
                if os.path.exists(lbk_path):
                    os.remove(lbk_path)
                os.rename(save_path, lbk_path)
        torch.save(state_dict, save_path)

    def load_network(self, load_path, network, strict=True):
        if isinstance(network, nn.DataParallel):
            network = network.module
        network.load_state_dict(torch.load(load_path), strict=strict)

    def save_training_state(self, epoch, iter_step, backup=False):
        '''Saves training state during training, which will be used for resuming'''
        state = {'epoch': epoch, 'iter': iter_step, 'schedulers': [], 'optimizers': []}
        for s in self.schedulers:
            state['schedulers'].append(s.state_dict())
        for o in self.optimizers:
            state['optimizers'].append(o.state_dict())
        state['python_rng'] = random.getstate()
        state['numpy_rng'] = np.random.get_state()
        state['torch_rng'] = torch.get_rng_state()
        state['cuda_rng'] = torch.cuda.get_rng_state()
        save_filename = '{}.state'.format('backup' if backup else iter_step)
        save_path = os.path.join(self.opt['path']['training_state'], save_filename)
        if backup:
            if os.path.exists(save_path):
                lbk_path = os.path.join(self.opt['path']['training_state'], 'backup-old.state')
                if os.path.exists(lbk_path):
                    os.remove(lbk_path)
                os.rename(save_path, lbk_path)
        torch.save(state, save_path)

    def resume_training(self, resume_state):
        '''Resume the optimizers and schedulers for training'''
        resume_optimizers = resume_state['optimizers']
        resume_schedulers = resume_state['schedulers']
        assert len(resume_optimizers) == len(self.optimizers), 'Wrong lengths of optimizers'
        assert len(resume_schedulers) == len(self.schedulers), 'Wrong lengths of schedulers'
        for i, o in enumerate(resume_optimizers):
            self.optimizers[i].load_state_dict(o)
        for i, s in enumerate(resume_schedulers):
            # Work around a bug in .state files from victorca25's BasicSR
            if isinstance(self.schedulers[i].milestones, Counter) and isinstance(s['milestones'], list):
                s['milestones'] = Counter(s['milestones'])
            self.schedulers[i].load_state_dict(s)
        if 'python_rng' in resume_state: # Allow old state files to load
            random.setstate(resume_state['python_rng'])
            np.random.set_state(resume_state['numpy_rng'])
            torch.set_rng_state(resume_state['torch_rng'])
            torch.cuda.set_rng_state(resume_state['cuda_rng'])

    def update_schedulers(self, train_opt):
        '''Update scheduler parameters if they are changed in the JSON configuration'''
        if train_opt['lr_scheme'] == 'StepLR':
            for i, s in enumerate(self.schedulers):
                if self.schedulers[i].step_size != train_opt['lr_step_size'] and train_opt['lr_step_size'] is not None:
                    print("Updating step_size from ",self.schedulers[i].step_size ," to", train_opt['lr_step_size'])
                    self.schedulers[i].step_size = train_opt['lr_step_size']
                #common
                if self.schedulers[i].gamma !=train_opt['lr_gamma'] and train_opt['lr_gamma'] is not None:
                    print("Updating lr_gamma from ",self.schedulers[i].gamma," to", train_opt['lr_gamma'])
                    self.schedulers[i].gamma =train_opt['lr_gamma']
        if train_opt['lr_scheme'] == 'StepLR_Restart':
            for i, s in enumerate(self.schedulers):
                if self.schedulers[i].step_sizes != train_opt['lr_step_sizes'] and train_opt['lr_step_sizes'] is not None:
                    print("Updating step_sizes from ",self.schedulers[i].step_sizes," to", train_opt['lr_step_sizes'])
                    self.schedulers[i].step_sizes = train_opt['lr_step_sizes']
                if self.schedulers[i].restarts != train_opt['restarts'] and train_opt['restarts'] is not None:
                    print("Updating restarts from ",self.schedulers[i].restarts," to", train_opt['restarts'])
                    self.schedulers[i].restarts = train_opt['restarts']
                if self.schedulers[i].restart_weights != train_opt['restart_weights'] and train_opt['restart_weights'] is not None:
                    print("Updating restart_weights from ",self.schedulers[i].restart_weights," to", train_opt['restart_weights'])
                    self.schedulers[i].restart_weights = train_opt['restart_weights']
                if self.schedulers[i].clear_state != train_opt['clear_state'] and train_opt['clear_state'] is not None:
                    print("Updating clear_state from ",self.schedulers[i].clear_state," to", train_opt['clear_state'])
                    self.schedulers[i].clear_state = train_opt['clear_state']
                #common
                if self.schedulers[i].gamma !=train_opt['lr_gamma'] and train_opt['lr_gamma'] is not None:
                    print("Updating lr_gamma from ",self.schedulers[i].gamma," to", train_opt['lr_gamma'])
                    self.schedulers[i].gamma =train_opt['lr_gamma']
        if train_opt['lr_scheme'] == 'MultiStepLR':
            for i, s in enumerate(self.schedulers):
                if self.schedulers[i].milestones != train_opt['lr_steps'] and train_opt['lr_steps'] is not None:
                    if not list(train_opt['lr_steps']) == sorted(train_opt['lr_steps']):
                        raise ValueError('lr_steps should be a list of'
                             ' increasing integers. Got {}', train_opt['lr_steps'])
                    print("Updating lr_steps from ",list(self.schedulers[i].milestones) ," to", train_opt['lr_steps'])
                    if isinstance(self.schedulers[i].milestones, Counter):
                        self.schedulers[i].milestones = Counter(train_opt['lr_steps'])
                    else:
                        self.schedulers[i].milestones = train_opt['lr_steps']
                #common
                if self.schedulers[i].gamma !=train_opt['lr_gamma'] and train_opt['lr_gamma'] is not None:
                    print("Updating lr_gamma from ",self.schedulers[i].gamma," to", train_opt['lr_gamma'])
                    self.schedulers[i].gamma =train_opt['lr_gamma']
        if train_opt['lr_scheme'] == 'MultiStepLR_Restart':
            for i, s in enumerate(self.schedulers):
                if self.schedulers[i].milestones != train_opt['lr_steps'] and train_opt['lr_steps'] is not None:
                    if not list(train_opt['lr_steps']) == sorted(train_opt['lr_steps']):
                        raise ValueError('lr_steps should be a list of'
                             ' increasing integers. Got {}', train_opt['lr_steps'])
                    print("Updating lr_steps from ",list(self.schedulers[i].milestones) ," to", train_opt['lr_steps'])
                    if isinstance(self.schedulers[i].milestones, Counter):
                        self.schedulers[i].milestones = Counter(train_opt['lr_steps'])
                    else:
                        self.schedulers[i].milestones = train_opt['lr_steps']
                if self.schedulers[i].restarts != train_opt['restarts'] and train_opt['restarts'] is not None:
                    print("Updating restarts from ",self.schedulers[i].restarts," to", train_opt['restarts'])
                    self.schedulers[i].restarts = train_opt['restarts']
                if self.schedulers[i].restart_weights != train_opt['restart_weights'] and train_opt['restart_weights'] is not None:
                    print("Updating restart_weights from ",self.schedulers[i].restart_weights," to", train_opt['restart_weights'])
                    self.schedulers[i].restart_weights = train_opt['restart_weights']
                if self.schedulers[i].clear_state != train_opt['clear_state'] and train_opt['clear_state'] is not None:
                    print("Updating clear_state from ",self.schedulers[i].clear_state," to", train_opt['clear_state'])
                    self.schedulers[i].clear_state = train_opt['clear_state']
                #common
                if self.schedulers[i].gamma !=train_opt['lr_gamma'] and train_opt['lr_gamma'] is not None:
                    print("Updating lr_gamma from ",self.schedulers[i].gamma," to", train_opt['lr_gamma'])
                    self.schedulers[i].gamma =train_opt['lr_gamma']
        
