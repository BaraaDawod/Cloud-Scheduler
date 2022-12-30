
import pandas as pd
import json

def add5(x):
    return x + 5

def mult5(x):
    return x*5

def invertMatrixWrapper(col1, col2):
    df = pd.DataFrame([col1, col2])
    print(df)
    df = invertMatrix(df)
    print(df)
    df_json = pd.DataFrame(json.loads(df.to_json()))
    return df_json

def invertMatrix(dataframe_var):
    return dataframe_var.transpose()

def main():
    invertMatrixWrapper([1,2], [3,4])

if __name__ == "__main__":
    main()