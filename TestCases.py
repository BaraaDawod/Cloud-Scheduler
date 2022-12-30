import unittest
import os
import ChildVenv
import json
import multiprocessing
import Protocol


class TestCaseJson(unittest.TestCase):

    def setUp(self):
        venv = "portoptvenv"
        self.json_output = {
            "venv": venv,
            "module_absolute_path": __file__,
            "function": "addition_test_function",
            "parameters": []
        }
        self.json_folder_path = os. getcwd() + "\\test.json"
        self.childVenv = ChildVenv.ChildVenv(venv, self.json_folder_path, self.json_folder_path, 0)

        self.childVenv.print_queue = multiprocessing.Queue()
        self.childVenv.error_queue = multiprocessing.Queue()

    def testValidJson(self):
        self.json_output["parameters"] = [5, 10]
        expected_output = 15
        with open(self.json_folder_path, "w") as outfile:
            json.dump(self.json_output, outfile)


        output_json = self.childVenv.process_json_request(self.json_folder_path)
        self.assertEqual(output_json["error"], False)
        self.assertEqual(output_json["function_output"], expected_output)

    def InvalidFunctionName(self):
        self.json_output["function"] = "doesntexist"
        self.json_output["parameters"] = [5, 10]
        expected_output = 15

        with open(self.json_folder_path, "w") as outfile:
            json.dump(self.json_output, outfile)


        output_json = self.childVenv.process_json_request(self.json_folder_path)
        self.assertEqual(output_json["error"], False)
        self.assertEqual(output_json["function_output"], expected_output)

    def InvalidModuleName(self):
        self.json_output["module_absolute_path"] = os. getcwd() + "\\doesnotexist.py"

        with open(self.json_folder_path, "w") as outfile:
            json.dump(self.json_output, outfile)


        output_json = self.childVenv.process_json_request(self.json_folder_path)
        self.assertEqual(output_json["error"], True)
        self.assertIn(Protocol.MODULE_DOES_NOT_EXIST, output_json["function_output"])


def addition_test_function(num1: int, num2: int):
    return num1 + num2

if __name__ == "__main__":
    unittest.main()