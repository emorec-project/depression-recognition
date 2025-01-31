# -*- coding: utf-8 -*-


import tensorflow as tf
import os
import numpy as np
import glob
import csv
import re
import json
from sklearn.utils import shuffle
import tensorflow_hub as hub


def embed_useT(module):
    with tf.Graph().as_default():
        sentences = tf.placeholder(tf.string)
        embed = hub.Module(module)
        embeddings = embed(sentences)
        session = tf.train.MonitoredSession()
    return lambda x: session.run(embeddings, {sentences: x})


def clean_text(text):
    text = text.lower()
    text = re.sub(r"i'm", "i am", text)
    text = re.sub(r"i've", "i have", text)
    text = re.sub(r"he's", "he is", text)
    text = re.sub(r"she's", "she is", text)
    text = re.sub(r"that's", "that is", text)
    text = re.sub(r"that ' s", "that is", text)
    text = re.sub(r"it's", "it is", text)
    text = re.sub(r"that's", "that is", text)
    text = re.sub(r"where's", "where is", text)
    text = re.sub(r"what's", "what is", text)
    text = re.sub(r"\'ll", " will", text)
    text = re.sub(r"\'ve", " have", text)
    text = re.sub(r"\'re", " are", text)
    text = re.sub(r"\'d", " would", text)
    text = re.sub(r"won't", "will not", text)
    text = re.sub(r"don't", "do not", text)
    text = re.sub(r"can't", "can not", text)
    text = re.sub(r"hadn't", "had not", text)
    text = re.sub(r"didn't", "did not", text)
    text = re.sub(r"wouldn't", "would not", text)
    text = re.sub(r"weren't", "were not", text)
    text = re.sub(r"shouldn't", "should not", text)
    text = re.sub(r"doesn't", "does not", text)
    text = re.sub(r"couldn't", "could not", text)
    text = re.sub(r"isn't", "is not", text)
    text = re.sub(r"hasn't", "has not", text)
    text = re.sub(r"wasn't", "was not", text)
    text = re.sub(r"haven't", "have not", text)
    text = re.sub(r"didn't", "did not", text)
    text = re.sub(r"wouldnt'", "would not", text)
    text = re.sub(r"aren't", "are not", text)
    text = re.sub(r" em ", " them ", text)
    text = re.sub(r" there's ", " there is ", text)
    text = re.sub(r"let's", "let us", text)
    text = re.sub(r" who's ", " who is ", text)
    text = re.sub(r"\'s", "", text)
    text = re.sub(r"'", "", text)
    return text


def sent(data):
    words = [clean_text(x[2].strip()).strip() for x in data]
    words.pop(0)
    for ind, val in enumerate(words):
        a = val.split(' ')
        for ii, tp in enumerate(a):
            if (len(tp)):
                if (tp[0] == '<' and tp[-1] == '>'):
                    a[ii] = tp[1:-1]
                elif (tp[0] == '<'):
                    a[ii] = tp[1:]
        words[ind] = ' '.join(a).strip()
    return words


# bidirectional lstms
def network2(xx, bs, dp, kp):
    with tf.variable_scope('GEN'):
        lstms_fw = [tf.nn.rnn_cell.LSTMCell(size, use_peepholes=True) for size in [200, 200]]
        lstms_bw = [tf.nn.rnn_cell.LSTMCell(size, use_peepholes=True) for size in [200, 200]]

        drops_fw = [
            tf.contrib.rnn.DropoutWrapper(lstm, output_keep_prob=kp[0], variational_recurrent=False, dtype=tf.float32)
            for lstm in lstms_fw]
        drops_bw = [
            tf.contrib.rnn.DropoutWrapper(lstm, output_keep_prob=kp[1], variational_recurrent=False, dtype=tf.float32)
            for lstm in lstms_bw]

        lstm_output, output_fw, output_bw = tf.contrib.rnn.stack_bidirectional_dynamic_rnn(cells_fw=drops_fw,
                                                                                           cells_bw=drops_bw, inputs=xx,
                                                                                           dtype=tf.float32)
        fs = tf.reduce_sum(lstm_output, 1)

        logits = tf.nn.dropout(fs, keep_prob=dp)
        logits = tf.layers.batch_normalization(tf.nn.relu(tf.layers.dense(logits, 500)))

        logits = tf.nn.dropout(logits, keep_prob=dp)
        logits = tf.layers.batch_normalization(tf.nn.relu(tf.layers.dense(logits, 100)))
        logits = tf.nn.dropout(logits, keep_prob=dp)
        logits = tf.layers.batch_normalization(tf.nn.relu(tf.layers.dense(logits, 60)))
        logits = tf.layers.dense(logits, 1)

        return logits


def main():
    embed_fn = embed_useT('./USE/')
    embedding_matrix = []
    train_target = []
    m = []
    pth = ["./ASR_transcripts/*ript.csv"]
    for cnt, p in enumerate(pth):
        for filename in glob.glob(p):
            train_target.append(filename.split("/")[-1].split(".")[0][:-11])
            with open(filename, "rt") as f:
                data = csv.reader(f)
                msg_txt = sent(data)
                m.append(len(msg_txt))
                emb = embed_fn(msg_txt)
                a = np.zeros((400 - emb.shape[0], 512))
                x = np.vstack((a, emb))
                embedding_matrix.append(x)

    embedding_matrix = np.asarray(embedding_matrix)

    X = tf.placeholder(tf.float32, shape=[None, 400, 512])
    keep_prob = tf.placeholder(tf.float32)
    drpouts = tf.placeholder(tf.float32)
    batch_size = tf.placeholder(tf.int32, [], name='batch_size')
    logits = network2(X, batch_size, drpouts, keep_prob)
    saver = tf.train.Saver()
    path = "./AVEC_BOW_TrTeAVEC_ValDAIC/model.ckpt"

    ss = [i for i in train_target if 'test' in i]
    ss.sort()

    ch_data, ch_lbl = [], []
    for ix in ss:
        if ix in train_target and ('test') in ix:
            ch_data.append(embedding_matrix[train_target.index(ix)])

    ch_data = np.asarray(ch_data)

    sess = tf.Session()
    saver.restore(sess, path)
    print('model_restored')
    test_labels = sess.run(logits, feed_dict={X: ch_data, keep_prob: [1.0, 1.0], drpouts: 1.0, batch_size: len(ch_data)})

    tl = test_labels.tolist()

    cvv = [['Participant_id', 'Score']]

    for ik, jk in enumerate(ss):
        cvv.append([jk, str(round(tl[ik][0]))])

    with open('./DDS_IIITS_1_test_results.csv', 'w', newline='') as csvFile:
        writer = csv.writer(csvFile)
        writer.writerows(cvv)


if __name__ == '__main__':
    main()