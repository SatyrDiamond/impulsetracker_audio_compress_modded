import it214
import numpy as np
from external.easybinrw import easybinrw

dt_header = np.dtype([
	('num_samples', '<I'), 
	('bits', '<B'), 
	('hz', '<B'), 
	('channels', '<B'), 
	])

dt_chanpart = np.dtype([
	('type', '<B'), 
	('pos', '<I'), 
	('mix_from_chan', '<B'), 
	('size', '<I'), 
	])
# ================================================== ENCODE ==================================================

ENABLE_MIXING = 1

def encode_chunk(sampdata, is16):
	datal = []

	datal.append([0, sampdata])

	a_comp = it214.IT214Compressor(sampdata, is16, False)
	a_out_data = a_comp.get_data()
	datal.append([1, a_out_data])
	
	b_comp = it214.IT214Compressor(sampdata, is16, True)
	b_out_data = b_comp.get_data()
	datal.append([2, b_out_data])
	
	if not (min(sampdata) or max(sampdata)): datal.append([3, b''])

	bestcomps = [len(x[1]) for x in datal]
	bestc = bestcomps.index(min(bestcomps))

	out_type, out_data = datal[bestc]

	if not out_type: print('E', out_type, len(sampdata), len(out_data))

	return out_type, out_data

def encode(filename, is16, numchans):
	ebrw_readstr = easybinrw.binread()
	ebrw_readstr.load_file(filename)
	num_samples = 0x1000
	outdata = b''

	total_numsamples = num_samples*numchans

	while ebrw_readstr.remaining():
		print((ebrw_readstr.state.end-ebrw_readstr.remaining())/ebrw_readstr.state.end, end=' ')
		ebrw_writestr = easybinrw.binwrite()
		chunk_write = easybinrw.binwrite()

		sampdata = ebrw_readstr.list_int_u16(total_numsamples) if is16 else ebrw_readstr.list_int_u8(total_numsamples)

		header_data = np.zeros(1, dt_header)
		header_data['hz'] = 0
		header_data['bits'] = 16 if is16 else 8
		header_data['channels'] = numchans
		header_data['num_samples'] = len(sampdata)//numchans
		chunk_write.raw(header_data.tobytes())

		outt = []
		pos = 0

		for n in range(numchans):
			indata = sampdata[n::numchans]

			mix_from_chan = 0

			if is16 and ENABLE_MIXING:
				if not n: 
					firstaudio_data = indata
					out_type, out_data = encode_chunk(indata.tobytes(), is16)
				elif n==1: 
					chan_l = np.frombuffer(firstaudio_data.tobytes(), np.int16)
					chan_r = np.frombuffer(indata.tobytes(), np.int16)
					combmix = chan_r-chan_l
					oout_type, oout_data = encode_chunk(indata.tobytes(), is16)
					cond1 = (min(chan_r)<min(combmix))
					cond2 = (max(chan_r)>max(combmix))
					if cond1 or cond2:
						combmix = combmix.astype(np.int32)
						cout_type, cout_data = encode_chunk(combmix.astype(np.int16).tobytes(), is16)

						if len(cout_data)<len(out_data):
							mix_from_chan = 1
							out_type, out_data = cout_type, cout_data
						else:
							out_type, out_data = oout_type, oout_data
					else:
						out_type, out_data = oout_type, oout_data
			else:
				out_type, out_data = encode_chunk(indata.tobytes(), is16)


			header_data = np.zeros(1, dt_chanpart)
			header_data['type'] = out_type
			header_data['pos'] = pos
			pos += len(out_data)
			header_data['mix_from_chan'] = mix_from_chan
			header_data['size'] = len(out_data)
			chunk_write.raw(header_data.tobytes())
			outt.append(out_data)
			print(out_type, mix_from_chan, end=' ')
		print()

		for x in outt:
			chunk_write.raw(x)

		outchunk = chunk_write.getvalue()
		ebrw_writestr.int_u32(len(outchunk))
		ebrw_writestr.raw(outchunk)
		yield ebrw_writestr.getvalue()

def encode_file_stereo(filename, is16, outfilename):
	of = open(outfilename, 'wb')
	for x in encode(filename, is16, 2):
		of.write(x)
	of.close()

def encode_file(filename, is16, outfilename):
	of = open(outfilename, 'wb')
	for x in encode(filename, is16, 1):
		of.write(x)
	of.close()

# ================================================== ENCODE ==================================================

def decode_chunk(ebrw_readstr):
	chunk_size = ebrw_readstr.int_u32()
	startpos = ebrw_readstr.tell()

	ebrw_readstr.seek(startpos)

	header_data = np.frombuffer(ebrw_readstr.raw(dt_header.itemsize), dt_header)[0]
	numchans = header_data['channels']
	chan_data = np.frombuffer(ebrw_readstr.raw(dt_chanpart.itemsize*numchans), dt_chanpart)
	headafterpos = ebrw_readstr.tell()

	num_samples = header_data['num_samples']
	is_16 = header_data['bits']==16

	outchans = []
	for n, chan_part in enumerate(chan_data):
		chan_mix = chan_part['mix_from_chan']
		print(chan_mix, chan_part['type'], end=' - ')

		chanpos = headafterpos+chan_part['pos']
		ebrw_readstr.seek(chanpos)
		data = ebrw_readstr.raw(chan_part['size'])

		auddata = decode_audio(chan_part['type'], data, num_samples, is_16)
		auddata = np.frombuffer(auddata, dtype=(np.uint16 if is_16 else np.uint8)).copy()
		auddata.dtype = (np.int16 if is_16 else np.int8)

		outdata = np.zeros(num_samples, dtype=(np.uint16 if is_16 else np.uint8))
		outdata[0:len(auddata)] = auddata

		if chan_mix:
			org_aud = outchans[chan_mix-1]
			outdata[0:len(org_aud)] = outdata[0:len(org_aud)]+org_aud
		else:
			outdata[0:len(auddata)] = auddata
		outchans.append(outdata)

	print()

	nextchunk = startpos+chunk_size
	ebrw_readstr.seek(nextchunk)
	return header_data, is_16, outchans

def decode_audio(out_type, data, sampsize, is16):
	if out_type==0:
		return data
	elif out_type==1:
		decomp = it214.IT214Decompressor(data, sampsize, is16)
		xdata = decomp.get_data()
		return np.array(xdata, dtype=(np.uint16 if is16 else np.uint8)).tobytes()
	elif out_type==2:
		decomp = it214.IT214Decompressor(data, sampsize, is16)
		xdata = decomp.get_data()
		base = 0
		if is16:
			for i in range(len(xdata)):
				base += xdata[i]
				base &= 0xFFFF
				xdata[i] = base
		else:
			for i in range(len(xdata)):
				base += xdata[i]
				base &= 0xFF
				xdata[i] = base
		return np.array(xdata, dtype=(np.uint16 if is16 else np.uint8)).tobytes()
	elif out_type==3:
		return b'\0'*(sampsize*2)
	else:
		print('unknown type', out_type)
		return b'\0'*sampsize

def decode(filename, channels):
	ebrw_readstr = easybinrw.binread()
	ebrw_readstr.load_file(filename)
	outdata = b''
	while ebrw_readstr.remaining(): 
		print(ebrw_readstr.remaining(), end=' ')
		header_data, is_16, chunk = decode_chunk(ebrw_readstr)

		numchans = int(header_data['channels'])
		num_samples = int(header_data['num_samples'])
		current_arr = np.zeros(num_samples*numchans, dtype=(np.uint16 if is_16 else np.uint8))

		for chan in range(numchans):
			chunkdata = chunk[chan]
			current_arr[chan:len(chunkdata)*numchans:numchans] = chunkdata
		outdata += current_arr.tobytes()

	return outdata

def decode_file(filename, is16, outfilename):
	od = decode(filename, 2)
	of = open(outfilename, 'wb')
	of.write(od)

#encode_file_stereo('test.raw', True, 'out.it215')
encode_file('test.raw', True, 'out.it215')


decode_file('out.it215', True, 'outdec_mono.pcm')