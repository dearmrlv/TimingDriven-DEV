# DATE'25 "Timing-Driven Global Placement by Efficient Critical Path Extraction"
We provide the implementation of the method proposed in the paper. It is built upon the popular open-source infrastructure [DREAMPlace](https://github.com/limbo018/DREAMPlace).

## Build with Docker

We highly recommend the use of Docker to enable a smooth environment configuration.

The following steps are borrowed from [DREAMPlace](https://github.com/limbo018/DREAMPlace) repository. We make minor revisions to make it more clear.

1. Get the code and put it in folder `DATE25-TDP`.

2. Get the container:

- Option 1: pull from the cloud [limbo018/dreamplace](https://hub.docker.com/r/limbo018/dreamplace).

  ```
  docker pull limbo018/dreamplace:cuda
  ```

- Option 2: build the container.

  ```
  docker build . --file Dockerfile --tag your_name/dreamplace:cuda
  ```

3. Enter bash environment of the container. Replace `limbo018` with your name if option 2 is chosen in the previous step.

- Option 1: Run with GPU on Linux.

  ```
  docker run --gpus 1 -it -v $(pwd):/DATE25-TDP limbo018/dreamplace:cuda bash
  ```

- Option 2: Run with CPU on Linux.

  ```
  docker run -it -v $(pwd):/DATE25-TDP limbo018/dreamplace:cuda bash
  ```

4. ` cd /DATE25-TDP`.

5. Build.

   ```
   mkdir build
   cd build
   cmake .. 
   make
   make install
   ```

6. Get benchmarks: download the cases here: https://drive.google.com/file/d/1xeauwLR9lOxnYvsK2JGPSY0INQh8VuE4/view?usp=sharing. Unzip the package and put it in the following directory:

   ```
   install/benchmarks/iccad2015.ot
   ```

## Test

Run our method on case superblue1 of ICCAD2015 timing-driven placement contest:

```
python dreamplace/Placer.py test/iccad2015.pin2pin/$case.json
```

Or you can run all 8 cases by:

```
cd install
./run.sh
```

The iccad2015 contest's official evaluation kit can be found at [Google Drive link](https://drive.google.com/file/d/1BAjEfWxN2dZOtt2-qlgF-qO7D-KHJthX/view?usp=sharing).

## Baseline Reproduction Results

Reproduced on this machine with GPU execution on a single `RTX 4060 Ti (16380 MiB)`.

- Detailed repo map, scripted setup, and reproduction notes: `README.research.md`
- Machine-readable summaries: `results/baselines/full_suite_template.csv` and `results/baselines/smoke_summary.csv`
- Reported `TNS` and `WNS` below are the repository's native OpenTimer metrics, not the external ICCAD2015 official evaluator.

| case | method | TNS | WNS | HPWL | runtime | status |
| --- | --- | --- | --- | --- | --- | --- |
| superblue1 | DREAMPlace 4.0 | -86.205780 | -14.138051 | 5.764892E+09 | 402.854 | ok |
| superblue1 | Efficient-TDP | -15.665889 | -8.323147 | 4.188897E+08 | 542.367 | ok |
| superblue3 | DREAMPlace 4.0 | -50.278965 | -15.729451 | 1.619536E+09 | 502.761 | ok |
| superblue3 | Efficient-TDP | -19.854089 | -11.724317 | 4.628147E+08 | 554.147 | ok |
| superblue4 | DREAMPlace 4.0 | -153.626060 | -13.704465 | 1.786124E+09 | 241.609 | ok |
| superblue4 | Efficient-TDP | -90.259830 | -9.161039 | 3.180224E+08 | 1324.106 | ok |
| superblue5 | DREAMPlace 4.0 | -101.250460 | -27.685633 | 2.608756E+09 | 454.780 | ok |
| superblue5 | Efficient-TDP | -65.440080 | -24.220008 | 4.852562E+08 | 748.797 | ok |
| superblue7 | DREAMPlace 4.0 | -61.622710 | -15.395518 | 8.582195E+08 | 597.971 | ok |
| superblue7 | Efficient-TDP | -37.190520 | -15.395518 | 5.980916E+08 | 757.736 | ok |
| superblue10 | DREAMPlace 4.0 | -660.061080 | -23.671605 | 6.766032E+09 | 759.398 | ok |
| superblue10 | Efficient-TDP | -564.221600 | -23.441709 | 9.145873E+08 | 1866.491 | ok |
| superblue16 | DREAMPlace 4.0 | -64.993815 | -14.681975 | 1.677648E+09 | 292.204 | ok |
| superblue16 | Efficient-TDP | -22.604395 | -7.841117 | 4.726394E+08 | 319.362 | ok |
| superblue18 | DREAMPlace 4.0 | -47.919910 | -11.780133 | 2.065470E+09 | 244.688 | ok |
| superblue18 | Efficient-TDP | -15.976826 | -6.969738 | 2.338593E+08 | 270.556 | ok |

## DCF First Implementation

- Implementation note: `docs/dcf_first_impl.md`
- Code map: `docs/dcf_code_map.md`
- DCF configs: `test/iccad2015.dcf/` and `install/test/iccad2015.dcf/`
- DCF is integrated as a new timing weighting scheme, `net_weighting_scheme: "dcf"`, and reuses the existing pin-to-pin attraction path.

| case | DREAMPlace 4.0 TNS | DREAMPlace 4.0 WNS | DREAMPlace 4.0 HPWL | DREAMPlace 4.0 runtime | Efficient-TDP TNS | Efficient-TDP WNS | Efficient-TDP HPWL | Efficient-TDP runtime | DCF v1 TNS | DCF v1 WNS | DCF v1 HPWL | DCF v1 runtime |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| superblue1 | -86.205780 | -14.138051 | 5.764892E+09 | 402.854 | -15.665889 | -8.323147 | 4.188897E+08 | 542.367 | -48.398495 | -23.075512 | 4.448847E+08 | 317.407 |
| superblue16 | -64.993815 | -14.681975 | 1.677648E+09 | 292.204 | -22.604395 | -7.841117 | 4.726394E+08 | 319.362 | -99.327000 | -23.684324 | 4.887341E+08 | 231.157 |
| superblue18 | -47.919910 | -11.780133 | 2.065470E+09 | 244.688 | -16.047550 | -7.073299 | 2.338333E+08 | 262.014 | -17.725619 | -7.188731 | 2.373461E+08 | 226.864 |

All listed DCF runs completed without crash or NaN.

## Caution

The default configuration for Critical Path Extraction uses 8 threads to accommodate various CPU cores and RAM capacities, impacting only the execution speed without affecting timing performance. For reproducing the speeds reported in the paper, adjust the thread count to 52 as specified in `DATE25-TDP/thirdparty/OpenTimer/ot/timer/path.cpp` at line 426.
