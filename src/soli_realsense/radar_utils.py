#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Apr  8 04:38:11 2021

@author: mrawe14
"""
import numpy as np
import matplotlib.pyplot as plt

#@title Utils
# Range profile (aka preprocessed)
#%% Standard radar pre-processing library 
def compute_rp_complex(chirp_raw, zpf = 1):
    n_rbins = chirp_raw.shape[0]

    # window
    window = np.blackman(n_rbins).astype(np.float32)
    window /= np.linalg.norm(window)

    chirp_raw = chirp_raw - np.mean(chirp_raw)  
    # range processing
    chirp_raw = chirp_raw.astype(np.float32)
    chirp_raw *= window
    chirp_raw = chirp_raw - np.mean(chirp_raw)
    rp_complex = np.fft.fft(chirp_raw, n=n_rbins * zpf)[:int(n_rbins * zpf / 2)] / n_rbins

    return rp_complex

def get_rp_data(json_data):
    rp_data = list()
    for burst in np.asarray(json_data['bursts']):
        chirps_in_burst = np.asarray(burst['chirps']).reshape(16,3,-1)
        for channels_in_chirp in chirps_in_burst:
            rp_chirp = list()
            for chirp_per_channel in channels_in_chirp:
                chirp = np.asarray(chirp_per_channel)
                rp_chirp.append(compute_rp_complex(chirp))
            rp_data.append(rp_chirp)
    return np.asarray(rp_data)

def remove_clutter(range_data, clutter_alpha):
    assert range_data.ndim == 3
    clutter_map = 0
    nchirp, nchan, szr = range_data.shape
    range_clutter = range_data.copy()
    if clutter_alpha != 0:
        clutter_map = range_data[0]
        for ic in range(1, nchirp):
            clutter_map = (clutter_map * clutter_alpha + range_data[ic, ...] * (1.0 - clutter_alpha))
            range_clutter[ic, ...] -=  clutter_map
    return range_clutter

def get_chirp_timestamps(json_data):
    timestamps = []
    for burst in json_data['bursts']:
          timestamps.append(burst['timestamp_ms'])
    return np.asarray(timestamps)

def plot_abs_data(data):
    for channel_idx in range(data.shape[1]):
        fig = plt.figure(figsize=(6,2), dpi=300)
        ax = fig.add_subplot(111)
        plt.title('channel {}'.format(channel_idx))
        plt.imshow(np.abs(data[:,channel_idx,:].transpose()), origin='lower', cmap=plt.get_cmap('jet'), interpolation='none', aspect='auto')
        cbar = plt.colorbar()
        cbar.set_label('Amplitude',rotation=270,labelpad=10)
        plt.tight_layout()
        plt.xlabel('Chirp #')
        plt.ylabel('Range (a.u.)')
        plt.grid(False)
        plt.show()

def get_crd_data(json_data, clutter_coeff=0.9, num_chirps_per_burst=16):
    rp_data = get_rp_data(json_data)
    rp_clutter = remove_clutter(rp_data, clutter_coeff)

    window = np.blackman(num_chirps_per_burst).astype(np.float32)
    window /= np.linalg.norm(window)

    rp_transposed = np.transpose(rp_clutter, (1, 0, 2))
    result = []
    for channel_data in rp_transposed:
        channel_data = np.reshape(channel_data, (channel_data.shape[0] // num_chirps_per_burst, num_chirps_per_burst, channel_data.shape[1]))
        crp_per_channel = []
        for burst in channel_data:
            burst = np.transpose(burst)
            crp_burst = []
            for data in burst:
                data = data * window
                data = np.fft.fft(data)
                crp_burst.append(data)
            crp_burst = np.asarray(crp_burst)
            crp_per_channel.append(crp_burst)
        crp_per_channel = np.asarray(crp_per_channel)
        result.append(crp_per_channel)
    result = np.asarray(result)
    result = np.transpose(result,(1, 0, 2, 3))
    result = np.roll(result, result.shape[3]//2, axis=3)
    return result

def plot_crd_data(crd_data, path=""):
    num_channels=crd_data.shape[1]
    for i,frame_crd in enumerate(crd_data):
        print(i)
        fig,axs=plt.subplots(nrows=1,ncols=3,gridspec_kw={'width_ratios':(1,1,1)},figsize = (8.53,4.8), dpi=100)
        for channel_id in range(num_channels):  
            #plt.subplot(1, num_channels, channel_id + 1,sharey=True)
            im = axs[channel_id].imshow(np.abs(frame_crd[channel_id,:,:]), origin='lower', cmap=plt.get_cmap('jet'), interpolation='none', aspect='auto')
            axs[channel_id].set_title('ch' + str(channel_id))
            axs[channel_id].set_xlabel('velocity (a.u.)')
            axs[channel_id].set_xticks(ticks = [0,4,8,12])
            axs[channel_id].set_xticklabels(labels=(-8,-4,0,4))
            #divider = make_axes_locatable(axs[channel_id])
            #cax = divider.append_axes('right', size='5%', pad=0.05)
            #cbar = fig.colorbar(im,cax=cax)
            #cbar.set_label('amplitude (a.u.)',rotation=270,labelpad=10)
            axs[channel_id].set_ylabel('range (a.u.)')

        plt.tight_layout()
        plt.grid(False)
        # plt.savefig(r"{}/img{}.png".format(path,i))
        plt.show()
        # plt.close()

# %%
#%%
def find_nearest(array,values):
    """
    

    Parameters
    ----------
    array : array-like
        the target array from which to search nearest elements
    values : array-like
        the list of values.

    Returns
    -------
    idxs : array
        the nearest elements of 'array' for each element of 'values'. Used to resample a data series to match the timestamps of another data series.

    """
    idxs = np.zeros(len(values))
    for i,value in enumerate(values):
        idx = np.searchsorted(array, value, side="left")
        if idx > 0 and (idx == len(array) or math.fabs(value - array[idx-1]) < math.fabs(value - array[idx])):
            idxs[i] = idx-1
        else:
            idxs[i] = idx
    return idxs

def plot_crd_image_data(crd_data,image_data,path,start=0):
    """Helper method to plot crd frames and images"""
    num_channels=crd_data.shape[1]
    for i,frame_crd in tqdm(enumerate(crd_data)):
        plt.figure(figsize = (8.53,2*4.8), dpi=100)
        for channel_id in range(num_channels):  
            plt.subplot(2, 3, (channel_id + 1))
            plt.imshow(np.abs(frame_crd[channel_id,:,:]), origin='lower', cmap=plt.get_cmap('jet'), interpolation='none', aspect='auto')
            plt.title('ch' + str(channel_id))
            plt.xlabel('velocity (a.u.)')
            plt.xticks(ticks = [0,4,8,12],labels=(-8,-4,0,4))
            plt.ylabel('range (a.u.)')
        plt.subplot(2,1,2)
        plt.imshow(image_data[i], vmin=0, vmax=7, cmap='viridis_r', interpolation='none', aspect='auto')
        cbar = plt.colorbar()
        cbar.set_label('depth (m)',rotation=270, labelpad=15)
        plt.tight_layout()
        plt.grid(False)
        # plt.savefig(r"{}/img{}.png".format(path,i+start))
        #plt.show()    
        plt.close()
        
def find_nearest(array,values):
    """
    

    Parameters
    ----------
    array : array-like
        the target array from which to search nearest elements
    values : array-like
        the list of values.

    Returns
    -------
    idxs : array
        the nearest elements of 'array' for each element of 'values'. Used to resample a data series to match the timestamps of another data series.

    """
    idxs = np.zeros(len(values))
    for i,value in enumerate(values):
        idx = np.searchsorted(array, value, side="left")
        if idx > 0 and (idx == len(array) or math.fabs(value - array[idx-1]) < math.fabs(value - array[idx])):
            idxs[i] = idx-1
        else:
            idxs[i] = idx
    return idxs

def plot_crd_image_data(crd_data,image_data,path,start=0):
    """Helper method to plot crd frames and images"""
    num_channels=crd_data.shape[1]
    for i,frame_crd in tqdm(enumerate(crd_data)):
        plt.figure(figsize = (8.53,2*4.8), dpi=100)
        for channel_id in range(num_channels):  
            plt.subplot(2, 3, (channel_id + 1))
            plt.imshow(np.abs(frame_crd[channel_id,:,:]), origin='lower', cmap=plt.get_cmap('jet'), interpolation='none', aspect='auto')
            plt.title('ch' + str(channel_id))
            plt.xlabel('velocity (a.u.)')
            plt.xticks(ticks = [0,4,8,12],labels=(-8,-4,0,4))
            plt.ylabel('range (a.u.)')
        plt.subplot(2,1,2)
        plt.imshow(image_data[i], vmin=0, vmax=7, cmap='viridis_r', interpolation='none', aspect='auto')
        cbar = plt.colorbar()
        cbar.set_label('depth (m)',rotation=270, labelpad=15)
        plt.tight_layout()
        plt.grid(False)
        # plt.savefig(r"{}/img{}.png".format(path,i+start))
        #plt.show()    
        plt.close()