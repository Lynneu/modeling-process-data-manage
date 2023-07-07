# Dataflow Modeling Process Dataset

This repository contains a comprehensive dataset of the dataflow diagram modeling process, based on log data collected from a dataflow modeling platform over four semesters. The dataset is cleaned, encoded, and augmented with feature extraction to provide rich and detailed information about modeling operations and details. This can be of great value for analysis and understanding of the modeling process in the domain of Model-Driven Engineering (MDE).

## Features

The dataset records not only modeling operations and elements, but also details like dataflow directions, connections between elements, and timestamps of operations. This gives insights into aspects like efficiency of modeling, time spent on different tasks, and the sequence of operations performed.

Specific features include:

- OperationTimeDuration: The duration of each operation.
- ConsecutiveOperationTimeInterval: The interval between consecutive operations.
- OperationType: The type of each operation.
- Undo/Redo Operation Details: Captures uncertainty in operations and elements.
- Dataflow Details: Information about dataflow direction and connected elements.

## Potential Applications

The potential applications of this dataset include:

- Error prediction and correction: By training a model on this dataset, we can predict and correct errors in real-time during the modeling process.
- Intelligent modeling recommendations: Newcomers to dataflow modeling could receive suggestions for their next steps, easing their learning process.
- Understanding interplay between modeling process and outcome: Project managers and team leaders can gain insights into team workflows, allowing for process optimization and quality improvement.

## Data Collection and Processing

The data is collected over four semesters from a dataflow modeling platform. The raw log data was first cleaned to remove incorrect entries and incomplete records. Then, crucial features were extracted, including modeling operation and details. The selection of features considered their potential usefulness for subsequent research and applications.

## Contact

For any questions or further information, please contact lynneuuu@gmail.com