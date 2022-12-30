import json
import datetime
import sys

try:
    path = ''
    if len(sys.argv) == 1:
        path = "S:\\TFM\\Programs\\PROD\\bcitfm\\api"
    else:
        path = "C:\\Source\\Repo\\TotalFundManagement\\bcitfm\\api"
    venvs = ['base', 'portoptvenv', 'tfmdashvenv']
    venvs = ['base']
    count = 0
    for i in range(0,1):
        for venv in venvs:
            time_stamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            filename = f"{time_stamp}_{count}.json"
            print(filename)

            json_output = {
                "venv": venv,
                "module_absolute_path": "C:\\Source\\Repo\\TotalFundManagement\\bcitfm\\api\\test_module.py",
                "function": "add5",
                "parameters": [10]
            }

            with open(path + "\\request\\" + filename, "w") as outfile:
                json.dump(json_output, outfile)
            
            filename = filename.replace('.json', '.signal')
            open(path + "\\request\\" + filename, 'a').close()
            count += 1

except Exception as e:
    print(e)