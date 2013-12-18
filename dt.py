import svmlight
import time
import math
from numpy import arange
from numpy import meshgrid
from os import listdir
from os.path import isfile, join
from scipy import ndimage
from skimage import feature
from skimage import io
from skimage import transform

# cProfile + RunSnakeRun
# line_profiler 
# timeit 

# Omit regions
# L1 space regions

# Global Variables
window_width = 256
window_height = 80
orientations = 9
cell = 16
block = 3
scale_factor = 0.90

positive_threshold = 1.0

nms_neighborhood = 75
nms_neighbors = 6
nms_across_adjacent_scales = 1

def distance(x1,y1,x2,y2):
	return int(round(math.sqrt(((x1 - x2) ** 2) + ((y1 - y2) ** 2))))

def pix_to_blocks(num_pixels):
	return (num_pixels / cell) - block + 1

def split_vector(vector, source_width, source_height):

	width = pix_to_blocks(source_width)
	height = pix_to_blocks(source_height)
	w = pix_to_blocks(window_width)
	h = pix_to_blocks(window_height)
	orients = orientations * block * block

	x_list = [((vec / orients) % width) + (w / block) - 1 for vec in xrange(0, len(vector), orients)]
	y_list = [((vec / orients) / width) + (h / block) - 1 for vec in xrange(0, len(vector), orients)]

	vectors = {}
	for vec in xrange(0, len(vector), orients):
		index = int(vec / orients)
		origin_x = x_list[index]
		origin_y = y_list[index]
		
		points = []
		for i in xrange(0, w):
			for j in xrange(0, h):
				points.append(((origin_x - i) * cell, (origin_y - j) * cell))
					
		for a,b in points:
			index = str(a) + "^" + str(b)
			if index not in vectors:
				vectors[index] = list(vector[vec: vec + orients])
			else:
				vectors[index] += vector[vec: vec + orients]
	
	testing_data_keys = []
	testing_data_tuples = []
	for key, vector in vectors.iteritems():
		vals = []
		num = 1
		for val in vector:
			vals.append((num, float(val)))
			num += 1
		testing_data_tuples.append((0,vals))
		testing_data_keys.append(key)
	
	return testing_data_keys, testing_data_tuples

print "Loading Model"
model = svmlight.read_model('svm-model.dat')

testing_data = []
directory = "tests"
filenames = [ f for f in listdir(directory + "/originals/") if isfile(join(directory + "/originals/",f)) and f[0] != "." ]

start_time = time.time()
counter = 0

for filename in filenames:

	print "\n-----------------------------------"
	print directory + "/originals/" + filename + "\n"
	
	img = io.imread(directory + "/originals/" + filename, as_grey=True)
	output = io.imread(directory + "/originals/" + filename, as_grey=False)

	output_width = len(output[0])
	output_height = len(output)
		
	points = []

	centerx_list = []
	centery_list = []
	radx_list = []
	rady_list = []

	iteration = 1
	max_pred = -1

	while len(img[0]) >= window_width and len(img) >= window_height:

		print iteration
		hog = feature.hog(img, orientations=orientations, pixels_per_cell=(cell, cell), cells_per_block=(block, block), normalise=True)
		testing_data_keys, testing_data_tuples = split_vector(hog.tolist(), len(img[0]), len(img))
		predictions = svmlight.classify(model, testing_data_tuples)
		
		scale = (1.0 / scale_factor) ** iteration
		for i in xrange(len(predictions)):
			prediction = float(predictions[i])
			
			if prediction >= positive_threshold:
				max_pred = max(max_pred, prediction)
				coordinate = testing_data_keys[i].split("^")
				centerx = int(int(coordinate[0]) * scale)
				centery = int(int(coordinate[1]) * scale)
				radx = int((window_width / 2) * scale)
				rady = int((window_height / 2) * scale)
			
				centerx_list.append(centerx)
				centery_list.append(centery)
				radx_list.append(radx)
				rady_list.append(rady)

				points.append((centerx, centery, radx, rady, prediction, iteration))

		img = transform.rescale(img, scale_factor)
		iteration += 1

	for c in range(10):
		neighborhoods = []
		for point in points:

			centerx = point[0]
			centery = point[1]
			radx = point[2]
			rady = point[3]
			prediction = point[4]
			iteration = point[5]
			relative_nms_neighborhood = nms_neighborhood * ((1.0 / scale_factor) ** iteration)

			peak = False
			neighbors = []
			for compare_point in points:
			
				compare_centerx = compare_point[0]
				compare_centery = compare_point[1]
				compare_prediction = compare_point[4]
				compare_iteration = compare_point[5]
				scale_nms_neighborhood = ((nms_neighborhood * ((1.0 / scale_factor) ** iteration)) + (nms_neighborhood * ((1.0 / scale_factor) ** compare_iteration)) ) / 2 

				if iteration == compare_iteration and distance(centerx, centery, compare_centerx, compare_centery) <= relative_nms_neighborhood and prediction <= compare_prediction:
					neighbors.append(compare_point)
				elif abs(iteration - compare_iteration) <= nms_across_adjacent_scales and distance(centerx, centery, compare_centerx, compare_centery) <= scale_nms_neighborhood and prediction <= compare_prediction:
					neighbors.append(compare_point)

			if len(neighbors) > 0:
				neighbors.sort(key=lambda x:float(x[4]))
				neighbors = neighbors[-nms_neighbors:]

				prediction_total = 0.0
				for neighbor in neighbors:
					prediction_total += neighbor[4]

				for neighbor in neighbors:
					if prediction == neighbor[4]:
						average_centerx = 0
						average_centery = 0
						average_radx = 0
						average_rady = 0
						average_prediction = 0.0
						average_iteration = 0

						for neighbor in neighbors:
							average_centerx += neighbor[0] * (neighbor[4] / prediction_total)
							average_centery += neighbor[1] * (neighbor[4] / prediction_total)
							average_radx += neighbor[2] * (neighbor[4] / prediction_total)
							average_rady += neighbor[3] * (neighbor[4] / prediction_total)
							average_prediction += neighbor[4]
							average_iteration += neighbor[5]
						
						average_prediction /= len(neighbors)
						average_iteration /= len(neighbors)

						neighborhoods.append((int(average_centerx), int(average_centery), int(average_radx), int(average_rady), average_prediction, int(average_iteration)))
						break

		points = list(neighborhoods)

	for point in points:
		centerx = point[0]
		centery = point[1]
		radx = point[2]
		rady = point[3]
		color = [0,255,0]

		print centerx, centery, radx, rady, point[4], point[5]

		for i in xrange(-rady, rady):
			y = (centery + i)
			x1 = centerx - radx
			x2 = centerx + radx

			if 0 <= y and y < output_height:
				if 0 <= x1 and x1 < output_width and (len(centerx_list) > 1 or i > 0):
					output[y][x1] = color

				if 0 <= x2 and x2 < output_width and (len(centerx_list) > 1 or i < 0):
					output[y][x2] = color
		
		for i in xrange(-radx, radx):
			x = (centerx + i)
			y1 = centery - rady
			y2 = centery + rady

			if 0 <= x and x < output_width:
				if 0 <= y1 and y1 < output_height and (len(centerx_list) > 1 or i > 0):
					output[y1][x] = color

				if 0 <= y2 and y2 < output_height and (len(centerx_list) > 1 or i < 0):
					output[y2][x] = color	
		
	io.imsave(directory + "/heatmaps/" + filename, output)
	counter += 1
		
if counter > 0:
	total_time = float(time.time() - start_time)
	print "Time: %.2f sec (Average: %.2f sec)" %(total_time, total_time / counter)

