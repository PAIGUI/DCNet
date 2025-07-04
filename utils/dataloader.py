import os
import cv2
import torch.utils.data as data
import torchvision.transforms as transforms
from PIL import Image
import random
import numpy as np
from PIL import ImageEnhance


# data augumentation
def cv_random_flip(img, gt):
    # left right flip
    flip_flag = random.randint(0, 1)
    if flip_flag == 1:
        img = img.transpose(Image.FLIP_LEFT_RIGHT)
        gt = gt.transpose(Image.FLIP_LEFT_RIGHT)
    return img, gt


def randomCrop(image, gt):
    border = 30
    image_width = image.size[0]
    image_height = image.size[1]
    crop_win_width = np.random.randint(image_width - border, image_width)
    crop_win_height = np.random.randint(image_height - border, image_height)
    random_region = (
        (image_width - crop_win_width) >> 1, (image_height - crop_win_height) >> 1, (image_width + crop_win_width) >> 1,
        (image_height + crop_win_height) >> 1)
    return image.crop(random_region), gt.crop(random_region)


def randomRotation(image, gt):
    mode = Image.BICUBIC
    if random.random() > 0.8:
        random_angle = np.random.randint(-15, 15)
        image = image.rotate(random_angle, mode)
        gt = gt.rotate(random_angle, mode)
    return image, gt


def colorEnhance(image):
    bright_intensity = random.randint(5, 15) / 10.0
    image = ImageEnhance.Brightness(image).enhance(bright_intensity)
    contrast_intensity = random.randint(5, 15) / 10.0
    image = ImageEnhance.Contrast(image).enhance(contrast_intensity)
    color_intensity = random.randint(0, 20) / 10.0
    image = ImageEnhance.Color(image).enhance(color_intensity)
    sharp_intensity = random.randint(0, 30) / 10.0
    image = ImageEnhance.Sharpness(image).enhance(sharp_intensity)
    return image


def randomGaussian(image, mean=0.1, sigma=0.35):
    def gaussianNoisy(im, mean=mean, sigma=sigma):
        for _i in range(len(im)):
            im[_i] += random.gauss(mean, sigma)
        return im

    img = np.asarray(image)
    width, height = img.shape
    img = gaussianNoisy(img[:].flatten(), mean, sigma)
    img = img.reshape([width, height])
    return Image.fromarray(np.uint8(img))


def randomPeper_eg(img):
    img = np.array(img)

    noiseNum = int(0.0015 * img.shape[0] * img.shape[1])
    for i in range(noiseNum):
        randX = random.randint(0, img.shape[0] - 1)
        randY = random.randint(0, img.shape[1] - 1)
        if random.randint(0, 1) == 0:
            img[randX, randY] = 0
        else:
            img[randX, randY] = 255
    return Image.fromarray(img)


class CamImgTrain(data.Dataset):
    """训练集"""

    def __init__(self, image_root, gt_root, image_size):
        self.images = [image_root + f for f in os.listdir(image_root) if f.endswith('.jpg') or f.endswith('.png')]
        self.gts = [gt_root + f for f in os.listdir(gt_root) if f.endswith('.jpg') or f.endswith('.png')]
        self.images = sorted(self.images)
        self.gts = sorted(self.gts)
        self.filter_files()
        self.dataset_size = len(self.images)
        self.image_size = image_size
        self.img_transform = transforms.Compose([
            transforms.Resize((self.image_size, self.image_size)),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406],
                                 [0.229, 0.224, 0.225])])
        self.gt_transform = transforms.Compose([
            transforms.Resize((self.image_size, self.image_size)),
            transforms.ToTensor()])


    def __getitem__(self, index):
        image = self.rgb_loader(self.images[index])
        gt = self.binary_loader(self.gts[index])


        # data augumentation
        image, gt = cv_random_flip(image, gt)
        image, gt = randomCrop(image, gt)
        image, gt= randomRotation(image, gt)

        image = colorEnhance(image)
        gt = randomPeper_eg(gt)

        image = self.img_transform(image)
        gt = self.gt_transform(gt)
        return image, gt

    def filter_files(self):
        assert len(self.images) == len(self.gts)
        images = []
        gts = []
        for img_path, gt_path in zip(self.images, self.gts):
            img = Image.open(img_path)
            gt = Image.open(gt_path)
            if img.size == gt.size:
                images.append(img_path)
                gts.append(gt_path)
        self.images = images
        self.gts = gts

    def rgb_loader(self, path):
        with open(path, 'rb') as f:
            img = Image.open(f)
            return img.convert('RGB')

    def binary_loader(self, path):
        with open(path, 'rb') as f:
            img = Image.open(f)
            return img.convert('L')
        
    def prompt_loader(self,prompt):
        """Load a feature map from a .npy file, complete to three channels, normalize, and convert to RGB.

        Args:
            prompt (str): The file path to the .npy file.

        Returns:
            Image: A PIL Image in RGB format.
        """
        # Load the feature map
        image_array = np.load(prompt)

        # 确保读取的数组是正确的形状 [1024, 1280, 2]
        if image_array.shape != (1024, 1280, 2):
            raise ValueError(f"Expected shape (1024, 1280, 2), but got {image_array.shape}")

        # 创建一个形状为 [1024, 1280, 3] 的零数组
        rgb_array = np.zeros((1024, 1280, 3), dtype=np.float32)

        # 将前两个通道赋值给 RGB 数组的前两个通道
        rgb_array[..., 0] = image_array[..., 0]  # R 通道
        rgb_array[..., 1] = image_array[..., 1]  # G 通道
        # B 通道保持为 0

        # 归一化到 [0, 255] 范围
        rgb_array -= rgb_array.min()  # 将最小值减去
        rgb_array /= rgb_array.max()   # 除以最大值
        rgb_array *= 255               # 映射到 [0, 255]

        # 转换为 uint8 类型
        rgb_array = rgb_array.astype(np.uint8)

        # 创建 PIL 图像
        return Image.fromarray(rgb_array, 'RGB')


    def __len__(self):
        return self.dataset_size


class test_dataset:
    """load test dataset (batchsize=1)"""

    def __init__(self, image_root, gt_root, test_size):
        self.test_size = test_size
        self.images = [image_root + f for f in os.listdir(image_root) if f.endswith('.jpg') or f.endswith('.png')]
        self.gts = [gt_root + f for f in os.listdir(gt_root) if f.endswith('.tif') or f.endswith('.png')]
        self.images = sorted(self.images)
        self.gts = sorted(self.gts)
        self.transform = transforms.Compose([
            transforms.Resize((self.test_size, self.test_size)),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])])
        self.gt_transform = transforms.ToTensor()
        self.size = len(self.images)
        self.index = 0

    def load_data(self):
        image = self.rgb_loader(self.images[self.index])
        image = self.transform(image).unsqueeze(0)
        gt = self.binary_loader(self.gts[self.index])
        

        name = self.images[self.index].split('/')[-1]
        if name.endswith('.jpg'):
            name = name.split('.jpg')[0] + '.png'
        self.index += 1
        self.index = self.index % self.size
        return image, gt, name

    def rgb_loader(self, path):
        with open(path, 'rb') as f:
            img = Image.open(f)
            return img.convert('RGB')

    def binary_loader(self, path):
        with open(path, 'rb') as f:
            img = Image.open(f)
            return img.convert('L')
        
    def prompt_loader(self,prompt):
        """Load a feature map from a .npy file, complete to three channels, normalize, and convert to RGB.

        Args:
            prompt (str): The file path to the .npy file.

        Returns:
            Image: A PIL Image in RGB format.
        """
        # Load the feature map
        image_array = np.load(prompt)

        # 确保读取的数组是正确的形状 [1024, 1280, 2]
        if image_array.shape != (1024, 1280, 2):
            raise ValueError(f"Expected shape (1024, 1280, 2), but got {image_array.shape}")

        # 创建一个形状为 [1024, 1280, 3] 的零数组
        rgb_array = np.zeros((1024, 1280, 3), dtype=np.float32)

        # 将前两个通道赋值给 RGB 数组的前两个通道
        rgb_array[..., 0] = image_array[..., 0]  # R 通道
        rgb_array[..., 1] = image_array[..., 1]  # G 通道
        # B 通道保持为 0

        # 归一化到 [0, 255] 范围
        rgb_array -= rgb_array.min()  # 将最小值减去
        rgb_array /= rgb_array.max()   # 除以最大值
        rgb_array *= 255               # 映射到 [0, 255]

        # 转换为 uint8 类型
        rgb_array = rgb_array.astype(np.uint8)

        # 创建 PIL 图像
        return Image.fromarray(rgb_array, 'RGB')


def get_loader(image_root, gt_root, batch_size, image_size, shuffle=True, num_workers=0, pin_memory=True):
    # `num_workers=0` for more stable training

    dataset = CamImgTrain(image_root, gt_root, image_size)
    data_loader = data.DataLoader(dataset=dataset,
                                  batch_size=batch_size,
                                  shuffle=shuffle,
                                  num_workers=num_workers,
                                  pin_memory=pin_memory)

    return data_loader