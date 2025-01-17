import math
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.autograd import Variable
from .channel_selection import channel_selection

__all__ = ['densenet']

"""
densenet with basic block.
"""
growR = 4


class BasicBlock(nn.Module):
    def __init__(self, inplanes, cfg, expansion=1, growthRate=growR, dropRate=0):
        super(BasicBlock, self).__init__()
        planes = expansion * growthRate
        self.bn1 = nn.BatchNorm2d(inplanes)

        # print(cfg)

        self.select = channel_selection(inplanes, cfg)
        # self.select = channel_selection(inplanes)
        self.conv1 = nn.Conv2d(cfg, growthRate, kernel_size=3,
                               padding=1, bias=False)
        self.relu = nn.ReLU(inplace=True)
        self.dropRate = dropRate

    def forward(self, x):
        out = self.bn1(x)
        out = self.select(out)
        out = self.relu(out)
        out = self.conv1(out)
        if self.dropRate > 0:
            out = F.dropout(out, p=self.dropRate, training=self.training)

        out = torch.cat((x, out), 1)

        return out


class Transition(nn.Module):
    def __init__(self, inplanes, outplanes, cfg):
        super(Transition, self).__init__()
        self.bn1 = nn.BatchNorm2d(inplanes)
        self.select = channel_selection(inplanes, cfg)
        # self.select = channel_selection(inplanes)
        self.conv1 = nn.Conv2d(cfg, outplanes, kernel_size=1,
                               bias=False)
        self.relu = nn.ReLU(inplace=True)

    def forward(self, x):
        out = self.bn1(x)
        out = self.select(out)
        out = self.relu(out)
        out = self.conv1(out)
        out = F.avg_pool2d(out, 2)
        return out


class densenet(nn.Module):

    def __init__(self, depth=40,
                 dropRate=0, dataset='cifar10', growthRate=growR, compressionRate=1, cfg=None):
        super(densenet, self).__init__()

        assert (depth - 4) % 3 == 0, 'depth should be 3n+4'
        n = (depth - 4) // 3
        block = BasicBlock

        self.growthRate = growthRate
        self.dropRate = dropRate

        if cfg is None:
            cfg = []
            start = growthRate * 2
            for _ in range(3):
                cfg.append([start + growthRate * i for i in range(n + 1)])
                start += growthRate * n
            cfg = [item for sub_list in cfg for item in sub_list]


            # cfg = [24, 36, 48, 60, 72, 84, 96, 108, 120, 132, 144, 156, 168, 168, 180, 192, 204, 216, 228, 240, 252,
            #        264, 276,
            #        288, 300, 312, 312, 324, 336, 348, 360, 372, 384, 396, 408, 420, 432, 444, 456]  # default


            # cfg = [16, 22, 26, 25, 22, 39, 33, 41, 53, 24, 39, 36, 152, 58, 58, 60, 63, 60, 56, 65, 71, 61, 78, 55, 66,
            #        285, 92, 87, 109, 124, 104, 114, 118, 111, 95, 95, 72, 61, 61]


        assert len(cfg) == 3 * n + 3, 'length of config variable cfg should be 3n+3'

        # self.inplanes is a global variable used across multiple
        # helper functions
        self.inplanes = growthRate * 2
        self.conv1 = nn.Conv2d(3, self.inplanes, kernel_size=3, padding=1,
                               bias=False)
        self.dense1 = self._make_denseblock(block, n, cfg[0:n])
        self.trans1 = self._make_transition(compressionRate, cfg[n])
        self.dense2 = self._make_denseblock(block, n, cfg[n + 1:2 * n + 1])
        self.trans2 = self._make_transition(compressionRate, cfg[2 * n + 1])
        self.dense3 = self._make_denseblock(block, n, cfg[2 * n + 2:3 * n + 2])
        self.bn = nn.BatchNorm2d(self.inplanes)
        self.select = channel_selection(self.inplanes, cfg[-1])
        # self.select = channel_selection(self.inplanes)
        self.relu = nn.ReLU(inplace=True)
        self.avgpool = nn.AvgPool2d(8)

        if dataset == 'cifar10':
            self.fc = nn.Linear(cfg[-1], 10)
        elif dataset == 'cifar100':
            self.fc = nn.Linear(cfg[-1], 100)

        # Weight initialization
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                n = m.kernel_size[0] * m.kernel_size[1] * m.out_channels
                m.weight.data.normal_(0, math.sqrt(2. / n))
            elif isinstance(m, nn.BatchNorm2d):
                m.weight.data.fill_(0.5)
                m.bias.data.zero_()

    def _make_denseblock(self, block, blocks, cfg):
        layers = []
        assert blocks == len(cfg), 'Length of the cfg parameter is not right.'
        for i in range(blocks):
            # Currently we fix the expansion ratio as the default value
            layers.append(block(self.inplanes, cfg=cfg[i], growthRate=self.growthRate, dropRate=self.dropRate))
            self.inplanes += self.growthRate

        return nn.Sequential(*layers)

    def _make_transition(self, compressionRate, cfg):
        # cfg is a number in this case.
        inplanes = self.inplanes
        outplanes = int(math.floor(self.inplanes // compressionRate))
        self.inplanes = outplanes
        return Transition(inplanes, outplanes, cfg)

    def forward(self, x):
        x = self.conv1(x)

        x = self.trans1(self.dense1(x))
        x = self.trans2(self.dense2(x))
        x = self.dense3(x)
        x = self.bn(x)
        x = self.select(x)
        x = self.relu(x)

        x = self.avgpool(x)
        x = x.view(x.size(0), -1)
        x = self.fc(x)

        return x
