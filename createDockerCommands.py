import glob, gzip, os, shutil, sys

analysis = sys.argv[1]
startIteration = int(sys.argv[2])
stopIteration = int(sys.argv[3])
memoryGigs = sys.argv[4]
swapMemoryGigs = sys.argv[5]
hoursMax = sys.argv[6]
numCores = sys.argv[7]
algorithmsFilePath = sys.argv[8]
dataToProcessFilePath = sys.argv[9]
outFileToCheck = sys.argv[10]
dockerOutFilePath = sys.argv[11]
shinyLearnerVersion = sys.argv[12]
imput_mode = sys.argv[13]
currentWorkingDir = os.path.dirname(os.path.realpath(__file__))

dockerCommandFilePaths = []

# Parse the algorithms file to find all possible algorithms
with open(algorithmsFilePath, 'r') as f:
  allAlgorithms = f.read().splitlines()
allAlgorithms = [x.replace('AlgorithmScripts/Classification/', '') for x in allAlgorithms if not x.startswith("#")]
allAlgorithms = [x.split("__")[0] for x in allAlgorithms]
allAlgorithms = set(allAlgorithms)

# Find all possible data combinations to process
with open(dataToProcessFilePath, 'r') as g:
  allDataToProcess = [x for x in g.read().splitlines() if not x.startswith("#")]

# Remove directory that contains the bash scripts that need to be executed
#   for each combination of dataset, algorithm, and iteration.
if os.path.exists(analysis + '_Commands/'):
  shutil.rmtree(analysis + '_Commands/')

for c in allDataToProcess:
  datasetID = c.split('\t')[0]
  classVar = c.split('\t')[1]

  input_data = list()
  dataset_path =  datasetID + '/'
  class_path = dataset_path + 'Class/' + classVar + '.txt'
  # grab the data types
  datatype_directory = c.split('\t')[2].split(',')
  number_of_datatypes = len(datatype_directory)
  # grab the data files for each data type

  for i in range(0, number_of_datatypes):
    datatype = datatype_directory[i]
    input_files = c.split('\t')[3 + i].split(',')
    for x in input_files:
      if datatype == "Expression":
        input_data.append(dataset_path + datatype + '/' + x + '.txt.gz')
      elif datatype == "Covariate":
        input_data.append(dataset_path + datatype + '/' + x + '.txt')
      elif datatype == "RPPA" or "SM":
        input_data.append(dataset_path + datatype+ '/' + x + ".tsv")
      else:
        input_data.append(dataset_path + datatype + '/' + x + '.ttsv')


  input_data.append(class_path)

  not_executed_algos = set()

  for i in range(startIteration, 1+stopIteration):
    print(analysis + ' ' + datasetID + ' ' + classVar + ' ' + 'iteration' + str(i))
    path = '/Analysis_Results/' + analysis + '/' + datasetID + '/' + classVar + '/iteration' + str(i) + '/*/' + outFileToCheck

    executed_algos = glob.glob(path)
    executed_algos = [x.split('/')[5].replace('__','/',3) for x in executed_algos]
    executed_algos = set(executed_algos)

    not_executed_algos = allAlgorithms - executed_algos

    for algo in not_executed_algos:
      algoName = algo.replace('/','__')

      # Build the part of the command that tells ShinyLearner which data files to parse
      data_all = ''
      for d in input_data:
        data_all = data_all + '--data "' + d + '" \\\n\t\t'

      # Where will the output files be stored?
      outDir = currentWorkingDir + "/Analysis_Results/" + analysis + '/' + datasetID + '/' + classVar + '/iteration' + str(i) + '/' + algoName + '/'

      # Build the bash script for this combination of dataset, algorithm, and iteration
      if imput_mode != "True":
        out = 'if [ ! -f ' + outDir + outFileToCheck + ' ]\nthen\n  docker run --memory ' + memoryGigs + 'G --memory-swap ' + swapMemoryGigs + 'G --rm -i \\\n\t-v "' + currentWorkingDir + '/InputData":"/InputData" \\\n\t-v "' + outDir + '":"/OutputData" \\\n\tsrp33/shinylearner:version' + shinyLearnerVersion + ' \\\n\ttimeout -s 9 ' + hoursMax + 'h \\\n\t"/UserScripts/classification_montecarlo" \\\n\t\t' + data_all + '--description ' + datasetID + '___' + classVar + '___iteration' + str(i) + ' \\\n\t\t--iterations 1 \\\n\t\t--classif-algo "AlgorithmScripts/Classification/' + algo + '*" \\\n\t\t --seed ' + str(i) + ' \\\n\t\t--verbose false \\\n\t\t--num-cores ' + numCores + '\nfi'
      else:
        out = 'if [ ! -f ' + outDir + outFileToCheck + ' ]\nthen\n  docker run --memory ' + memoryGigs + 'G --memory-swap ' + swapMemoryGigs + 'G --rm -i \\\n\t-v "' + currentWorkingDir + '/InputData":"/InputData" \\\n\t-v "' + outDir + '":"/OutputData" \\\n\tsrp33/shinylearner:version' + shinyLearnerVersion + ' \\\n\ttimeout -s 9 ' + hoursMax + 'h \\\n\t"/UserScripts/classification_montecarlo" \\\n\t\t' + data_all + '--impute true \\\n\t\t' + '--description ' + datasetID + '___' + classVar + '___iteration' + str(i) + ' \\\n\t\t--iterations 1 \\\n\t\t--classif-algo "AlgorithmScripts/Classification/' + algo + '*" \\\n\t\t --seed ' + str(i) + ' \\\n\t\t--verbose false \\\n\t\t--num-cores ' + numCores + '\nfi'

      # This is where the bash script will be stored
      commandFilePath = analysis + '_Commands/{}/{}/iteration{}/{}.sh'.format(datasetID, classVar, i, algoName)

      # Create the directory, if necessary, where the bash script will be stored
      if not os.path.exists(os.path.dirname(commandFilePath)):
        os.makedirs(os.path.dirname(commandFilePath))

      # Create the bash script
      with open(commandFilePath, 'w') as outFile:
        outFile.write(out + '\n')

      dockerCommandFilePaths.append(commandFilePath)

if len(dockerCommandFilePaths) == 0:
    print('All commands have been executed!')
else:
    # Create a file that indicates the location of all the bash scripts that need to be executed
    with open(dockerOutFilePath, 'w') as dockerOutFile:
        for command in dockerCommandFilePaths:
            dockerOutFile.write("bash {}\n".format(command))
