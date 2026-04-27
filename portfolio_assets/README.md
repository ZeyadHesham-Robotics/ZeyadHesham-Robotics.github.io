# portfolio_assets/

Photos and videos shown by the project cards and modal media gallery.

## Folder structure

```
portfolio_assets/
├── robotics/
│   ├── autonomous-mobile-robot/
│   │   ├── 1.jpg          ← card thumbnail + modal slide 1
│   │   ├── 2.jpg          ← modal slide 2
│   │   ├── 3.jpg          ← (optional, add to data.js gallery)
│   │   └── demo.mp4       ← (optional video)
│   ├── egsa-ground-station/
│   ├── rov/
│   ├── smart-wheelchair/
│   └── squash-bot/
├── embedded/
│   ├── daq-module/
│   ├── oscilloscope/
│   ├── ev-monitor/
│   └── motor-driver/
├── pcb/
│   ├── 32bit-ramps/
│   ├── agro-robot-motherboard/
│   ├── bottle-counter/
│   └── tawaf-bracelet/
├── mechanical/
│   ├── cornered-desk/
│   ├── mega-amr/
│   └── mine-ugv/
├── software/
│   ├── agricultural-monitoring/
│   ├── rc-car-control/
│   └── esp32-projects/
└── research/
    ├── kuka-robot-cv/
    ├── kuka-digital-twin/
    ├── safety-cell-guarding/
    ├── aruco-jig-improvement/
    └── palletizing-robot/
```

## Naming convention inside each project folder

```
1.jpg     ← required: card thumbnail + first slide in modal carousel
2.jpg     ← required: second slide
3.jpg     ← optional: third slide (add to data.js gallery to display)
4.jpg     ← optional: more slides allowed
demo.mp4  ← optional: short demo video (add to data.js gallery as type:"video")
```

The site reads paths from `assets/js/data.js`. By default it looks for `1.jpg` and `2.jpg`.
To add more slides or a video, open data.js and extend that project's `gallery: [...]` array.

Missing files fall back gracefully to the category emoji — your site never breaks.

## Adding more photos to a project

1. Drop the file into the project's folder, e.g.:
   `portfolio_assets/robotics/autonomous-mobile-robot/3.jpg`

2. Open `assets/js/data.js`, find that project, and add an entry to its `gallery`:
   ```js
   gallery:[
     {type:"image",src:"portfolio_assets/robotics/autonomous-mobile-robot/1.jpg",caption:"View 1"},
     {type:"image",src:"portfolio_assets/robotics/autonomous-mobile-robot/2.jpg",caption:"View 2"},
     {type:"image",src:"portfolio_assets/robotics/autonomous-mobile-robot/3.jpg",caption:"Pallet handling"}
   ],
   ```

## Adding a video

```js
gallery:[
  {type:"image",src:"portfolio_assets/robotics/autonomous-mobile-robot/1.jpg",caption:"View 1"},
  {type:"image",src:"portfolio_assets/robotics/autonomous-mobile-robot/2.jpg",caption:"View 2"},
  {type:"video",src:"portfolio_assets/robotics/autonomous-mobile-robot/demo.mp4",
   poster:"portfolio_assets/robotics/autonomous-mobile-robot/1.jpg",caption:"AMR demo"}
],
```

## Project ↔ folder map (24 projects)

| Slug                      | Folder                                              | 1.jpg in repo? |
|---------------------------|------------------------------------------------------|----------------|
| autonomous-mobile-robot   | robotics/autonomous-mobile-robot/                    | ✓ |
| egsa-ground-station       | robotics/egsa-ground-station/                        | ✓ |
| rov                       | robotics/rov/                                        | ✓ |
| smart-wheelchair          | robotics/smart-wheelchair/                           | ✓ |
| squash-bot                | robotics/squash-bot/                                 | ✓ |
| daq-module                | embedded/daq-module/                                 |   |
| oscilloscope              | embedded/oscilloscope/                               |   |
| ev-monitor                | embedded/ev-monitor/                                 | ✓ |
| motor-driver              | embedded/motor-driver/                               | ✓ |
| 32bit-ramps               | pcb/32bit-ramps/                                     |   |
| agro-robot-motherboard    | pcb/agro-robot-motherboard/                          | ✓ |
| bottle-counter            | pcb/bottle-counter/                                  | ✓ |
| tawaf-bracelet            | pcb/tawaf-bracelet/                                  | ✓ |
| cornered-desk             | mechanical/cornered-desk/                            |   |
| mega-amr                  | mechanical/mega-amr/                                 | ✓ |
| mine-ugv                  | mechanical/mine-ugv/                                 | ✓ |
| agricultural-monitoring   | software/agricultural-monitoring/                    |   |
| rc-car-control            | software/rc-car-control/                             |   |
| esp32-projects            | software/esp32-projects/                             |   |
| kuka-robot-cv             | research/kuka-robot-cv/                              |   |
| kuka-digital-twin         | research/kuka-digital-twin/                          |   |
| safety-cell-guarding      | research/safety-cell-guarding/                       |   |
| aruco-jig-improvement     | research/aruco-jig-improvement/                      |   |
| palletizing-robot         | research/palletizing-robot/                          |   |

✓ = `1.jpg` already in repo. Empty rows = drop your photo as `1.jpg` (and `2.jpg` if you have a second one).

## Recommended photo specs

- Format: JPEG (smaller) or PNG (lossless)
- Resolution: 1600×1000 px or larger; 16:10 / 16:9 aspect
- File size: ≤ 500 KB after compression (use https://squoosh.app)
- Video: MP4 (H.264 + AAC), ≤ 5 MB, ≤ 30 seconds
