# define dataset class to feed the model
import numpy as np 
import os
import sys
import time
import random
from IPython.display import display, HTML
import tensorflow as tf

def strip_consts(graph_def, max_const_size=32):
    """Strip large constant values from graph_def."""
    strip_def = tf.GraphDef()
    for n0 in graph_def.node:
        n = strip_def.node.add() 
        n.MergeFrom(n0)
        if n.op == 'Const':
            tensor = n.attr['value'].tensor
            size = len(tensor.tensor_content)
            if size > max_const_size:
                tensor.tensor_content = "<stripped %d bytes>"%size
    return strip_def

def show_graph(graph_def, max_const_size=32):
    """Visualize TensorFlow graph."""
    if hasattr(graph_def, 'as_graph_def'):
        graph_def = graph_def.as_graph_def()
    strip_def = strip_consts(graph_def, max_const_size=max_const_size)
    code = """
        <script>
          function load() {{
            document.getElementById("{id}").pbtxt = {data};
          }}
        </script>
        <link rel="import" href="https://tensorboard.appspot.com/tf-graph-basic.build.html" onload=load()>
        <div style="height:600px">
          <tf-graph-basic id="{id}"></tf-graph-basic>
        </div>
    """.format(data=repr(str(strip_def)), id='graph'+str(np.random.rand()))

    iframe = """
        <iframe seamless style="width:1200px;height:620px;border:0" srcdoc="{}"></iframe>
    """.format(code.replace('"', '&quot;'))
    display(HTML(iframe))

class ExpVal:
    def __init__(self,exp_a=0.97):
        self.val = None
        self.exp_a = exp_a
    def update(self,newval):
        if self.val == None:
            self.val = newval
        else:
            self.val = self.exp_a * self.val + (1 - self.exp_a) * newval
    def getval(self):
        return round(self.val,2)
    
class Tick:
    def __init__(self,tick=True):
        if tick == True:
            self._tick = time.time()
    def tick(self):
        self._tick = time.time()
    def tock(self):
        return round(time.time() - self._tick,2)

class FlowWrapper():
    def __init__(self,flow,shuffle=True):
        self.flow = flow
        self.randinds = list(range(len(flow)))
        self.shuffle = shuffle
        if shuffle == True:
            random.shuffle(self.randinds)
    
    def next_batch(self,batch_size):
        if len(self.randinds) < batch_size:
            self.randinds = list(range(len(self.flow)))
            if self.shuffle == True:
                random.shuffle(self.randinds)
        batch_inds,self.randinds = self.randinds[:batch_size],self.randinds[batch_size:]
        return self.flow[batch_inds]
    
class SortedEfficientFlowWrapper():
    def shuffle_all(self):
        print('shuffle')
        random.shuffle(self.randinds)
        finalarr = []
        for i in range(0,len(self.randinds),self.batch_size * self.secondary_batch):
            onearr = self.randinds[i:i + self.batch_size * self.secondary_batch]
            onearr = sorted(onearr)
            finalarr += onearr
        self.randinds = finalarr
    
    def __init__(self,flow,shuffle=True,secondary_batch=100,batch_size=64):
        self.flow = flow
        self.batch_size = batch_size
        self.randinds = list(range(len(flow)))
        self.shuffle = shuffle
        self.secondary_batch = secondary_batch
        if shuffle == True:
            self.shuffle_all()
    
    def next_batch(self,placeholder):
        if len(self.randinds) < self.batch_size:
            self.randinds = list(range(len(self.flow)))
            if self.shuffle == True:
                self.shuffle_all()
        batch_inds,self.randinds = self.randinds[:self.batch_size],self.randinds[self.batch_size:]
        return self.flow[batch_inds]
            
class Dataset():
    def __init__(self,*data):
        self._index_in_epoch = 0
        self._epochs_completed = 0
        self._data = data
        assert(len(self._data) >= 1)
        for one_data in self._data:
            assert(one_data.shape[0] == self._data[0].shape[0])
        self._num_examples = data[0].shape[0]

    @property
    def data(self):
        return self._data

    def next_batch(self,batch_size,shuffle = True):
        start = self._index_in_epoch
        if start == 0 and self._epochs_completed == 0:
            idx = np.arange(0, self._num_examples)  # get all possible indexes
            np.random.shuffle(idx)  # shuffle indexe
            self._data = [i[idx] for i in self.data]  # get list of `num` random samples

        # go to the next batch
        if start + batch_size > self._num_examples:
            self._epochs_completed += 1
            rest_num_examples = self._num_examples - start
            data_rest_part = [i[start:self._num_examples] for i in self.data]
            idx0 = np.arange(0, self._num_examples)  # get all possible indexes
            np.random.shuffle(idx0)  # shuffle indexes
            self._data = [i[idx0] for i in self.data]  # get list of `num` random samples

            start = 0
            self._index_in_epoch = batch_size - rest_num_examples #avoid the case where the #sample != integar times of batch_size
            end =  self._index_in_epoch  
            data_new_part = [i[start:end] for i in self.data]

            return [np.concatenate((i,j), axis=0) for i,j in zip(data_rest_part, data_new_part)]
        else:
            self._index_in_epoch += batch_size
            end = self._index_in_epoch
            return [i[start:end] for i in self.data]
            #return self._data[start:end],self._label[start:end]

class ProgressBar():
    def __init__(self,worksum,info="",auto_display=True):
        self.worksum = worksum
        self.info = info
        self.finishsum = 0
        self.auto_display = auto_display
    def startjob(self):
        self.begin_time = time.time()
    def complete(self,num):
        self.gaptime = time.time() - self.begin_time
        self.finishsum += num
        if self.auto_display == True:
            self.display_progress_bar()
    def display_progress_bar(self):
        percent = self.finishsum * 100 / self.worksum
        eta_time = self.gaptime * 100 / (percent + 0.001) - self.gaptime
        strprogress = "[" + "=" * int(percent // 2) + ">" + "-" * int(50 - percent // 2) + "]"
        str_log = ("%s %.2f %% %s %s/%s \t used:%ds eta:%d s" % (self.info,percent,strprogress,self.finishsum,self.worksum,self.gaptime,eta_time))
        sys.stdout.write('\r' + str_log)

def get_dataset(paths):
    dataset = []
    for path in paths.split(':'):
        path_exp = os.path.expanduser(path)
        classes = os.listdir(path_exp)
        classes.sort()
        nrof_classes = len(classes)
        for i in range(nrof_classes):
            class_name = classes[i]
            facedir = os.path.join(path_exp, class_name)
            if os.path.isdir(facedir):
                images = os.listdir(facedir)
                image_paths = [os.path.join(facedir,img) for img in images]
                dataset.append(ImageClass(class_name, image_paths))
  
    return dataset

class ImageClass():
    "Stores the paths to images for a given class"
    def __init__(self, name, image_paths):
        self.name = name
        self.image_paths = image_paths
  
    def __str__(self):
        return self.name + ', ' + str(len(self.image_paths)) + ' images'
  
    def __len__(self):
        return len(self.image_paths)

def split_dataset(dataset, split_ratio, mode):
    if mode=='SPLIT_CLASSES':
        nrof_classes = len(dataset)
        class_indices = np.arange(nrof_classes)
        np.random.shuffle(class_indices)
        split = int(round(nrof_classes*split_ratio))
        train_set = [dataset[i] for i in class_indices[0:split]]
        test_set = [dataset[i] for i in class_indices[split:-1]]
    elif mode=='SPLIT_IMAGES':
        train_set = []
        test_set = []
        min_nrof_images = 2
        for cls in dataset:
            paths = cls.image_paths
            np.random.shuffle(paths)
            split = int(round(len(paths)*split_ratio))
            if split<min_nrof_images:
                continue  # Not enough images for test set. Skip class...
            train_set.append(ImageClass(cls.name, paths[0:split]))
            test_set.append(ImageClass(cls.name, paths[split:-1]))
    else:
        raise ValueError('Invalid train/test split mode "%s"' % mode)
    return train_set, test_set

