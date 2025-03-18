# Pilot Progress
Various metrics to track pilot progression in a competition

## Setup data link
Create a symbolic link to the data directory 

```ln -s ~/Nextcloud/Paraglide/Competition-Pipeline data```

## Install
Install Python 3 and setup the correct dependencies. 

``` pip install -e . ```

Install local dependency `shortest-path` as well:

``` pip install -e ../shortest-path ```

## Run
Run `python pilot_progress.py` to run the analysis.
Run `python pilot_progression/pilot_progress.py` to extract the metrics and create the `kmz`-files.

## TODO
  * This is a mess: clean up
  * This repo should only focus on the computation of distance to goal and cleaning of the data.
  * The google earth part is kind of another project, similar to the airstart3d