import nltk

from server.abstract_server import AbstractServer
from server_blocks.message_protocol_util import MessageProtocolUtil
from server_blocks.reliable_connect import ReliableConnect


class BlocksServer(AbstractServer):

    def __init__(self, config, action_space, vocab=None):
        AbstractServer.__init__(self, config, action_space)
        self.config = config
        self.action_space = action_space
        self.vocab = vocab

        # Connect to simulator
        self.unity_ip = "0.0.0.0"

        self.PORT = config["port"]

        # Size of image
        image_height = config["image_height"]
        image_width = config["image_width"]
        self.connection = ReliableConnect(self.unity_ip, self.PORT, image_height, image_width)
        self.connection.connect()

        # Dataset specific parameters
        self.num_block = 20
        self.num_direction = 4
        use_stop = True
        if use_stop:
            self.num_actions = self.num_block * self.num_direction + 1  # 1 for stopping
        else:
            self.num_actions = self.num_block * self.num_direction

        # Create toolkit of message protocol between simulator and agent
        self.message_protocol_kit = MessageProtocolUtil(self.num_direction, self.num_actions, use_stop)

    def initialize_server(self):
        self.connection.initialize_server()

    @staticmethod
    def convert_text_to_indices(text, vocab, ignore_case=True):

        # Tokenize the text
        token_seq = nltk.word_tokenize(text)

        indices = []

        for token in token_seq:
            if ignore_case:
                ltoken = token.lower()
            else:
                ltoken = token
            if ltoken in vocab:
                indices.append(vocab[ltoken])
            else:
                indices.append(vocab["$UNK$"])

        return indices

    def reset_receive_feedback(self, next_data_point):

        datapoint_id = next_data_point.get_id()
        self.connection.send_message("Ok-Reset " + str(datapoint_id))

        img = self.connection.receive_image()
        response = self.connection.receive_message()

        (status_code, bisk_metric, _, instruction_string, trajectory) = \
            self.message_protocol_kit.decode_reset_message(response)

        # TODO this preprocessing is probably not the right place to send this data
        instruction = self.convert_text_to_indices(instruction_string, self.vocab)

        metadata = {"metric": bisk_metric, "status_code": status_code,
                    "instruction": instruction, "instruction_string": instruction_string, "trajectory": trajectory}
        return img, metadata

    def send_action_receive_feedback(self, action):

        action_str = self.action_space.get_action_name(action)

        # send message
        self.connection.send_message(action_str)

        img = self.connection.receive_image()
        response = self.connection.receive_message()
        (status_code, reward, _, reset_file_name) = self.message_protocol_kit.decode_message(response)

        metadata = {"status_code": status_code, "reset": reset_file_name}

        return img, reward, metadata

    def halt_and_receive_feedback(self):

        action = self.action_space.get_stop_action_index()
        action_str = self.action_space.get_action_name(action)

        # send message
        self.connection.send_message(action_str)

        img = self.connection.receive_image()
        response = self.connection.receive_message()
        (status_code, reward, _, reset_file_name) = self.message_protocol_kit.decode_message(response)

        metadata = {"status_code": status_code, "reset": reset_file_name}

        return img, reward, metadata

    def kill(self):
        self.connection.close()

    def clear_metadata(self):
        return False
