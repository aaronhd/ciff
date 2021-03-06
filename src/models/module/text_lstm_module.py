import torch
import numpy as np
import torch.nn as nn
import torch.nn.functional as F
from torch.autograd import Variable


def weights_init(m):
    classname = m.__class__.__name__
    if classname.find('Conv') != -1:
        weight_shape = list(m.weight.data.size())
        fan_in = np.prod(weight_shape[1:4])
        fan_out = np.prod(weight_shape[2:4]) * weight_shape[0]
        w_bound = np.sqrt(6. / (fan_in + fan_out))
        m.weight.data.uniform_(-w_bound, w_bound)
        m.bias.data.fill_(0)
    elif classname.find('Linear') != -1:
        weight_shape = list(m.weight.data.size())
        fan_in = weight_shape[1]
        fan_out = weight_shape[0]
        w_bound = np.sqrt(6. / (fan_in + fan_out))
        m.weight.data.uniform_(-w_bound, w_bound)
        m.bias.data.fill_(0)


class TextLSTMModule(nn.Module):
    """
    pytorch module for text part of model
    assumes input is two parts:
    (1) text_tokens is pytorch variable consisting of instructions in
        batch (dimensionality is BatchSize x SequenceLength
      - each element of sequence is integer giving word ID
      - SequenceLength is based on longest element of sequence
      - each non-longest sequence should be padded by 0's at the end,
        to make the tensor rectangular
      - sequences in batch should be sorted in descending-length order
    (2) text_length is pytorch tensor giving actual lengths of each sequence
        in batch (dimensionality is BatchSize)
    """
    def __init__(self, emb_dim, hidden_dim, vocab_size):
        super(TextLSTMModule, self).__init__()

        self.gru_hidden_size = hidden_dim
        self.input_size = vocab_size
        self.embedding = nn.Embedding(self.input_size, emb_dim)
        self.lstm = nn.LSTM(emb_dim, self.gru_hidden_size)

    def init_weights(self):
        self.apply(weights_init)

    def forward(self, instructions_batch):

        encoder_hidden = Variable(torch.zeros(1, 1, self.gru_hidden_size).cuda())
        encoder_cell = Variable(torch.zeros(1, 1, self.gru_hidden_size).cuda())
        for i in range(instructions_batch.data.size(1)):
            word_embedding = self.embedding(instructions_batch[0, i]).unsqueeze(0)
            _, (encoder_hidden, encoder_cell) = self.lstm(word_embedding, (encoder_hidden, encoder_cell))
        x_instr_rep = encoder_hidden.view(encoder_hidden.size(1), -1)

        return x_instr_rep
