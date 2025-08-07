import torch
from tqdm import tqdm
import models
from loss.utils import get_loss_function
from .utils import get_optimizer
from predictors.utils import get_predictor_and_adapter
class Trainer:
    """
    Trainer class that implement all the functions regarding training.
    All the arguments are passed through args."""
    def __init__(self, args, num_classes):
        self.args = args
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.net = models.utils.build_model(args.model, (args.pretrained == "True"), num_classes=num_classes, device=self.device, args=args)
        self.batch_size = args.batch_size

        self.optimizer = get_optimizer(args, self.net)

        if args.adapter == "True":
            self.set_train_mode((args.train_adapter == "True"), (args.train_net == "True"))
        self.predictor, self.adapter = get_predictor_and_adapter(args, num_classes, self.net, self.device)

        self.num_classes = num_classes
        self.loss_function = get_loss_function(args, self.predictor)

    def train_batch_without_adapter(self, data, target):
        #  split train_batch into train_batch_with_adapter and train_batch_without_adapter
        #  to avoid judging self.adapter is None in the loop.
        data = data.to(self.device)
        target = target.to(self.device)
        logits = self.net(data)
        loss = self.loss_function(logits, target)
        self.optimizer.zero_grad()
        loss.backward()
        self.optimizer.step()

    def train_batch_with_adapter(self, data, target):
        data = data.to(self.device)
        target = target.to(self.device)

        logits = self.adapter.adapter_net(self.net(data))
        loss = self.loss_function(logits, target)
        self.optimizer.zero_grad()
        loss.backward()
        self.optimizer.step()

    def train_epoch_without_adapter(self, data_loader, epoch=None):
        for data, target in tqdm(data_loader, desc=f"Epoch {epoch}"):
            self.train_batch_without_adapter(data, target)

    def train_epoch_with_adapter(self, data_loader):
        for data, target in tqdm(data_loader):
            self.train_batch_with_adapter(data, target)

    def train(self, data_loader, epochs):
        self.net.train()

        if self.adapter is None:
            for epoch in range(epochs):
                self.train_epoch_without_adapter(data_loader, epoch)
        else:
            for epoch in range(epochs):
                self.train_epoch_with_adapter(data_loader)

        if self.args.save_model == "True":
            models.utils.save_model(self.args, self.net)

    def adjust_learning_rate(self, optimizer, epoch):
        """Sets the learning rate to the initial LR decayed by 5 at 60, 120, 160 epochs"""
        if epoch == 60 or epoch == 120 or epoch == 160:
            for param_group in optimizer.param_groups:
                param_group['lr'] /= 5

    def set_train_mode(self, train_adapter, train_net):
        assert self.adapter is not None, print("The trainer does not have an adapter.")
        for param in self.adapter.adapter_net.parameters():
            param.requires_grad = train_adapter
        for param in self.net.parameters():
            param.requires_grad = train_net
