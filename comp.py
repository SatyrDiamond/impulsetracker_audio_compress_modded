import it214
import numpy as np
from external.easybinrw import easybinrw

def encode_chunk(sampdata, is16, channel):
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

	ebrw_writestr = easybinrw.binwrite()
	ebrw_writestr.int_u8(out_type + (channel<<4))
	ebrw_writestr.int_u16(len(sampdata))
	ebrw_writestr.int_u16(len(out_data))
	ebrw_writestr.raw(out_data)
	
	if not out_type: print('E', out_type, len(sampdata), len(out_data))

	return ebrw_writestr.getvalue()

def decode_chunk(ebrw_readstr, is16):
	out_type = ebrw_readstr.int_u8()
	sampdata = ebrw_readstr.int_u16()

	channel = out_type>>4
	out_type = out_type&15

	data = ebrw_readstr.raw(ebrw_readstr.int_u16())

	if not out_type: print('D', out_type, channel, sampdata, len(data))

	if out_type==0:
		return channel, data
	elif out_type==1:
		if is16: sampdata //= 2
		decomp = it214.IT214Decompressor(data, sampdata, is16)
		xdata = decomp.get_data()
		return channel, np.array(xdata, dtype=(np.uint16 if is16 else np.uint8)).tobytes()
	elif out_type==2:
		if is16: sampdata //= 2
		decomp = it214.IT214Decompressor(data, sampdata, is16)
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
		return channel, np.array(xdata, dtype=(np.uint16 if is16 else np.uint8)).tobytes()
	elif out_type==3:
		return channel, b'\0'*sampdata
	else:
		print('unknown type', out_type)
		return channel, b'\0'*sampdata

def encode_stereo(filename, is16):
	ebrw_readstr = easybinrw.binread()
	ebrw_readstr.load_file(filename)
	block_size = 0x1000
	outdata = b''
	while ebrw_readstr.remaining():
		sampdata = ebrw_readstr.list_int_u16(block_size*2) if is16 else ebrw_readstr.list_int_u8(block_size*2)
		outdata += encode_chunk(sampdata[0::2].tobytes(), is16, 0)
		outdata += encode_chunk(sampdata[1::2].tobytes(), is16, 1)
	return outdata

def encode(filename, is16):
	ebrw_readstr = easybinrw.binread()
	ebrw_readstr.load_file(filename)
	block_size = 0x1000
	outdata = b''
	while ebrw_readstr.remaining():
		sampdata = ebrw_readstr.raw(block_size)
		outdata += encode_chunk(sampdata, is16, 0)
	return outdata

def decode(filename, is16):
	ebrw_readstr = easybinrw.binread()
	ebrw_readstr.load_file(filename)
	outdata = b''
	while ebrw_readstr.remaining(): 
		chan, chunk = decode_chunk(ebrw_readstr, is16)
		if not chan: outdata += chunk
	return outdata

def decode_stereo(filename, is16):
	ebrw_readstr = easybinrw.binread()
	ebrw_readstr.load_file(filename)
	outdata = b''
	current_arr = None
	while ebrw_readstr.remaining(): 
		chan, chunk = decode_chunk(ebrw_readstr, is16)
		numsamples = len(chunk)
		if is16: 
			numsamples //= 2
			if len(chunk)%2: chunk = chunk[0:-1]
		if chan == 0:
			if current_arr is not None: outdata += current_arr.tobytes()
			current_arr = np.zeros(numsamples*2, dtype=(np.uint16 if is16 else np.uint8))
			td = np.frombuffer(chunk, dtype=(np.uint16 if is16 else np.uint8))
			current_arr[0::2] = td
			current_arr[1::2] = current_arr[0::2]

		if chan == 1:
			if current_arr is not None: 
				td = np.frombuffer(chunk, dtype=(np.uint16 if is16 else np.uint8))
				current_arr[1:len(chunk):2] = td[:len(current_arr[1:len(chunk):2])]
	if current_arr is not None: outdata += current_arr.tobytes()
	return outdata

def encode_file_stereo(filename, is16, outfilename):
	of = open(outfilename, 'wb')
	of.write( encode_stereo(filename, True) )
	of.close()

def encode_file(filename, is16, outfilename):
	of = open(outfilename, 'wb')
	of.write( encode(filename, True) )
	of.close()

def decode_file_stereo(filename, is16, outfilename):
	od = decode_stereo(filename, True)
	of = open(outfilename, 'wb')
	of.write(od)

def decode_file(filename, is16, outfilename):
	od = decode(filename, True)
	of = open(outfilename, 'wb')
	of.write(od)

encode_file_stereo('input.raw', True, 'out.it215')
decode_file_stereo('out.it215', True, 'outdec.pcm')
decode_file('out.it215', True, 'outdec_mono.pcm')