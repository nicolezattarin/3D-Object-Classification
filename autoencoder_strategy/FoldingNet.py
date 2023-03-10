import torch
import torch.nn as nn
import torch
import torch.nn as nn
import numpy as np
import itertools

import sys
sys.path.append('../')
sys.path.append('../autoencoder_strategy')
from ch_loss import ChamferLoss

class Encoder(nn.Module):
    def __init__(self, num_points):
        super(Encoder, self).__init__()
        self.num_points = num_points
        self.conv1 = nn.Conv1d(3, 64, 1)
        self.conv2 = nn.Conv1d(64, 128, 1)
        self.conv3 = nn.Conv1d(128, 1024, 1)
        self.bn1 = nn.BatchNorm1d(64)
        self.bn2 = nn.BatchNorm1d(128)
        self.bn3 = nn.BatchNorm1d(1024)

        self.fc1 = nn.Linear(1024 + 64, 1024)
        self.fc2 = nn.Linear(1024, 512)  # codeword dimension = 512


    def forward(self, input):
        input = input.transpose(2, 1)
        x = self.conv1(input)
        x = self.bn1(x)
        x = nn.ReLU()(x)


        local_feature = x  # save the  low level features to concatenate this global feature.
        x = self.conv2(x)
        x = self.bn2(x)
        x = nn.ReLU()(x)

        x = self.conv3(x)
        x = self.bn3(x)
        x = nn.ReLU()(x)

        x = torch.max(x, 2, keepdim=True)[0]

        global_feature = x.view(-1, 1024, 1).repeat(1, 1, self.num_points)

        feature = torch.cat([local_feature, global_feature], 1)  

        x = feature.transpose(1, 2)
        x = self.fc1(x)
        x = nn.ReLU()(x)
        x = self.fc2(x)


        return torch.max(x, 1, keepdim=True)[0]  # [bs, 1, 512]


class Decoder(nn.Module):
    def __init__(self, num_points=2048, m=2025):
        super(Decoder, self).__init__()
        self.n = num_points  # input point cloud size.
        self.m = m  # 45 * 45.
        self.meshgrid = [[-0.3, 0.3, 45], [-0.3, 0.3, 45]]
        self.mlp1 = nn.Sequential(
            nn.Conv1d(514, 256, 1),
            nn.ReLU(),
            nn.Conv1d(256, 64, 1),
            nn.ReLU(),
            nn.Conv1d(64, 3, 1),
        )

        self.mlp2 = nn.Sequential(
            nn.Conv1d(515, 256, 1),
            nn.ReLU(),
            nn.Conv1d(256, 64, 1),
            nn.ReLU(),
            nn.Conv1d(64, 3, 1),
        )

    def build_grid(self, batch_size):
        x = np.linspace(*self.meshgrid[0])
        y = np.linspace(*self.meshgrid[1])
        grid = np.array(list(itertools.product(x, y)))
        grid = np.repeat(grid[np.newaxis, ...], repeats=batch_size, axis=0)
        grid = torch.tensor(grid)
        return grid.float()

    def forward(self, input):
        input = input.transpose(1, 2).repeat(1, 1, self.m)  # [bs, 512, m]
        grid = self.build_grid(input.shape[0]).transpose(1, 2)  # [bs, 2, m]
        #if torch.cuda.is_available():
         #   grid = grid.cuda()
        concate1 = torch.cat((input, grid), dim=1)  # [bs, 514, m]
        after_folding1 = self.mlp1(concate1)  # [bs, 3, m]
        concate2 = torch.cat((input, after_folding1), dim=1)  # [bs, 515, m]
        after_folding2 = self.mlp2(concate2)  # [bs, 3, m]
        return after_folding2.transpose(1, 2)  # [bs, m ,3]


class FoldNet(nn.Module):
    def __init__(self, num_points):
        super(FoldNet, self).__init__()

        self.encoder = Encoder(num_points=num_points)
        self.decoder = Decoder(num_points=num_points)
        self.loss = ChamferLoss()

    def forward(self, input):
        codeword = self.encoder(input)
        output = self.decoder(codeword)
        return output, codeword
    
    def encode (self, input):
        codeword = self.encoder(input)
        return codeword

    def get_parameter(self):
        return list(self.encoder.parameters()) + list(self.decoder.parameters())

    def get_loss(self, input, output):

        return self.loss(input, output)


if __name__ == '__main__':
    input = torch.rand(1, 4000, 3)
    model = FoldNet(4000)
    sys.path.append('../')
    from utils import count_parameters
    count_parameters(model, input)