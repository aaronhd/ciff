import numpy as np
import torch
import torch.nn as nn
from torch.autograd import Variable
from torch.nn.utils.rnn import pack_padded_sequence, pad_packed_sequence
import torch.nn.functional as F

from utils.cuda import cuda_tensor, cuda_var


class TextPointerModule(nn.Module):
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
    def __init__(self, emb_dim, hidden_dim, vocab_size,
                 num_layers=1):
        super(TextPointerModule, self).__init__()
        self.emb_dim = emb_dim
        self.hidden_dim = hidden_dim
        self.vocab_size = vocab_size
        self.num_layers = num_layers

        self.embedding = nn.Embedding(vocab_size, emb_dim)
        self.lstm_f = nn.LSTM(emb_dim, hidden_dim, num_layers)
        self.lstm_b = nn.LSTM(emb_dim, hidden_dim, num_layers)

        self.final_dense = nn.Linear(hidden_dim * 4, hidden_dim)

    def forward(self, instructions_batch):
        token_lists, text_pointers = instructions_batch
        batch_size = len(token_lists)
        text_lengths = np.array([len(tokens) for tokens in token_lists])
        dims = (self.num_layers, batch_size, self.hidden_dim)
        hidden_f = (Variable(cuda_tensor(torch.zeros(*dims)), requires_grad=False),
                    Variable(cuda_tensor(torch.zeros(*dims)), requires_grad=False))
        hidden_b = (Variable(cuda_tensor(torch.zeros(*dims)), requires_grad=False),
                    Variable(cuda_tensor(torch.zeros(*dims)), requires_grad=False))

        # pad text tokens with 0's
        tokens_batch_f = [[] for _ in xrange(batch_size)]
        tokens_batch_b = [[] for _ in xrange(batch_size)]
        for i in xrange(batch_size):
            num_zeros = text_lengths[0] - text_lengths[i]
            tokens_batch_f[i] = token_lists[i] + [0] * num_zeros
            tokens_batch_b[i] = token_lists[i][::-1] + [0] * num_zeros
        tokens_batch_f = cuda_var(torch.from_numpy(np.array(tokens_batch_f)))
        tokens_batch_b = cuda_var(torch.from_numpy(np.array(tokens_batch_b)))

        # swap so batch dimension is second, sequence dimension is first
        tokens_batch_f = tokens_batch_f.transpose(0, 1)
        tokens_batch_b = tokens_batch_b.transpose(0, 1)
        emb_sentence_f = self.embedding(tokens_batch_f)
        emb_sentence_b = self.embedding(tokens_batch_b)
        packed_input_f = pack_padded_sequence(emb_sentence_f, text_lengths)
        packed_input_b = pack_padded_sequence(emb_sentence_b, text_lengths)
        lstm_out_packed_f, _ = self.lstm_f(packed_input_f, hidden_f)
        lstm_out_packed_b, _ = self.lstm_b(packed_input_b, hidden_b)

        # return average output embedding
        lstm_out_f, _ = pad_packed_sequence(lstm_out_packed_f)
        lstm_out_b, _ = pad_packed_sequence(lstm_out_packed_b)
        lstm_out_f = lstm_out_f.transpose(0, 1)
        lstm_out_b = lstm_out_b.transpose(0, 1)
        embeddings_list = []
        for i, (start_i, end_i) in enumerate(text_pointers):
            embeddings = []
            if start_i > 0:
                embeddings.append(lstm_out_f[i][start_i - 1])
            else:
                embeddings.append(cuda_var(torch.zeros(self.hidden_dim)))
            embeddings.append(lstm_out_f[i][end_i - 1])
            embeddings.append(lstm_out_b[i][start_i])
            if end_i < text_lengths[i]:
                embeddings.append(lstm_out_b[i][end_i])
            else:
                embeddings.append(cuda_var(torch.zeros(self.hidden_dim)))
            embeddings_list.append(torch.cat(embeddings).view(1, -1))

        embeddings_batch = torch.cat(embeddings_list)
        return embeddings_batch

