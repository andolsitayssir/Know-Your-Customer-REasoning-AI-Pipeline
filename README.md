# KYC AI pipeline
In this repository, we aime to Benchmark Small Language models in reasooning and agentic multi-steps tasks.

Models comparison and evaluation in two different agents:
1. Compliance Agent : 
Analysing a single JSON file, checking for error.
2. Cross-Check Agent : 
Receives 3 Different input files, checking for contradictions between the files.

### Minimum Requriements:
Local ollama

4GB GPU

### Command lines:
```
pip install -r requirements.txt
```

```
python scripts\run_benchmark.py ---model (model name)
```

```
python scripts\run_benchmark_agent4.py ---model (model name)
```






