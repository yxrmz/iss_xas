import pandas as pd
import numpy as np
from . import xray
from itertools import product
from copy import deepcopy


def load_apb_dataset_from_db(db, uid):
    hdr = db[uid]
    apb_dataset = deepcopy(list(hdr.data(stream_name='apb_stream', field='apb_stream'))[0])
    # apb_dataset = list(hdr.data(stream_name='apb_stream', field='apb_stream'))[0]
    energy_dataset =  list(hdr.data(stream_name='pb9_enc1',field='pb9_enc1'))[0]
    angle_offset = -float(hdr['start']['angle_offset'])

    # ch_offset_keys = [key for key in hdr.start.keys() if key.startswith('ch') and key.endswith('_offset')]
    # ch_offsets = np.array([hdr.start[key] for key in ch_offset_keys])

    ch_offsets = get_ch_properties(hdr.start, 'ch', '_offset')*1e3 #offsets are ib mV but the readings are in uV
    ch_gains = get_ch_properties(hdr.start, 'ch', '_amp_gain')

    apb_dataset.iloc[:, 1:] -= ch_offsets
    apb_dataset.iloc[:, 1:] /= 1e6
    apb_dataset.iloc[:, 1:] /= (10**ch_gains)

    return apb_dataset, energy_dataset, angle_offset



def get_ch_properties(hdr_start, start, end):
    ch_keys = [key for key in hdr_start.keys() if key.startswith(start) and key.endswith(end)]
    return np.array([hdr_start[key] for key in ch_keys])



def translate_apb_dataset(apb_dataset, energy_dataset, angle_offset,):
    data_dict= {}
    for column in apb_dataset.columns:
        if column != 'timestamp':
            adc = pd.DataFrame()
            adc['timestamp'] = apb_dataset['timestamp']
            adc['adc'] = apb_dataset[column]

            data_dict[column]=adc

    energy = pd.DataFrame()
    energy['timestamp'] = energy_dataset['ts_s'] + 1e-9 * energy_dataset['ts_ns']
    enc  = energy_dataset['encoder'].apply(lambda x: int(x) if int(x) <= 0 else -(int(x) ^ 0xffffff - 1))


    energy['encoder'] = xray.encoder2energy(enc, 360000, angle_offset)

    data_dict['energy'] = energy
    return data_dict


def load_apb_trig_dataset_from_db(db, uid, use_fall=True, stream_name='apb_trigger'):

    hdr = db[uid]
    t = hdr.table(stream_name=stream_name, fill=True)
    timestamps = t[stream_name][1]['timestamp'].values
    transitions = t[stream_name][1]['transition'].values
    n_0 = np.sum(transitions == 0)
    n_1 = np.sum(transitions == 1)
    n_all = np.min([n_0, n_1])
    if use_fall:
        apb_trig_timestamps = (timestamps[transitions == 1][:n_all] + timestamps[transitions == 0][:n_all])/2
    else:
        rises = timestamps[transitions == 1]
        apb_trig_timestamps = rises[:n_all] + np.mean(np.diff(rises))/2
    return apb_trig_timestamps


def load_xs3_dataset_from_db(db, uid, apb_trig_timestamps):
    hdr = db[uid]
    t = hdr.table(stream_name='xs_stream', fill=True)['xs_stream']
    n_spectra = t.size
    xs_timestamps = apb_trig_timestamps[:n_spectra]
    chan_roi_names = [f'CHAN{c}ROI{r}' for c, r in product([1, 2, 3, 4], [1, 2, 3, 4])]
    spectra = {}

    for j, chan_roi in enumerate(chan_roi_names):
        this_spectrum = np.zeros(n_spectra)

        for i in range(n_spectra):
            this_spectrum[i] = t[i+1][chan_roi]

        spectra[chan_roi] = pd.DataFrame(np.vstack((xs_timestamps, this_spectrum)).T, columns=['timestamp', chan_roi])

    return spectra



def load_pil100k_dataset_from_db(db, uid, apb_trig_timestamps, input_type='hdf5'):
    hdr = db[uid]
    spectra = {}
    if input_type == 'tiff':
        t = hdr.table(stream_name='pil100k_stream', fill=True)['pil100k_stream']
        n_images = t.shape[0]
        pil100k_timestamps = apb_trig_timestamps[:n_images]

        image_array = np.array([i for i in t])
        rois = hdr.start['roi']


        for j in range(4):
            x, y, dx, dy = rois[j]
            this_spectrum = np.sum(image_array[:, y: (y + dy), x: (x + dx)], axis=(1,2)) # NOTE : flipped X and Y

            spectra[f'pil100k_ROI{j+1}'] = pd.DataFrame(np.vstack((pil100k_timestamps, this_spectrum)).T, columns=['timestamp', f'pil100k_ROI{j+1}'])
    elif input_type == 'hdf5':
        t = hdr.table(stream_name='pil100k_hdf5_stream', fill=True)['pil100k_hdf5_stream']
        n_images = t.shape[0]
        pil100k_timestamps = apb_trig_timestamps[:n_images]
        keys = t[1].keys()
        _spectra = np.zeros((n_images, len(keys)))
        for i in range(0, n_images):
            for j, key in enumerate(keys):
                _spectra[i, j] = t[i+1][key]
        for j, key in enumerate(keys):
            spectra[key] =  pd.DataFrame(np.vstack((pil100k_timestamps, _spectra[:, j])).T, columns=['timestamp', f'pil100k_ROI{j+1}'])

    return spectra






def plot_normalized(x, y, factor=1):
    x = np.array(x)
    y = np.array(y)

    y_norm = (y - y.min())/factor
    plt.plot(x, y_norm)


def plot_normalized_scan(db, uid, factor=1):
    hdr = db[uid]
    x = list(hdr.data('hhm_energy'))
    y = list(hdr.data('pil100k_stats1_total'))
    plot_normalized(x, y, factor)





