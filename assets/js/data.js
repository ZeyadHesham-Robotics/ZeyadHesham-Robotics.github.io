/* =====================================================================
   Zeyad Hesham — Portfolio Data
   =====================================================================
   This file holds the content you edit most often:
     - CATEGORIES : the filter chips shown above the project grid
     - SKILLS     : the core-competencies list in section 01
     - PROJECTS   : the full project catalogue rendered in section 02
     - statusConfig    : label + color for each project status
     - categoryEmojis  : fallback emoji when a project has no photo
     - categoryNames   : display names for category ids

   To add a project: append a new object to the PROJECTS array.
   Required fields: slug, title, category, status, year, description,
   techStack, image (optional). See existing entries for the full shape.
   ===================================================================== */

/* ───── Categories & Skills ───── */
const CATEGORIES = [
    { id: "all",        name: "All" },
    { id: "robotics",   name: "Robotics" },
    { id: "embedded",   name: "Embedded" },
    { id: "pcb",        name: "PCB" },
    { id: "mechanical", name: "Mechanical" },
    { id: "software",   name: "Software" },
    { id: "research",   name: "R&D" }
];

const SKILLS = [
    "Robotics & Autonomous Systems",
    "Embedded Systems (ARM, AVR, ESP32)",
    "PCB Design & Electronics",
    "Mechanical Design (SolidWorks, CAD)",
    "Control Systems (LabVIEW, PLC, VFD)",
    "Real-time Operating Systems (ROS)",
    "Computer Vision & Image Processing",
    "Industrial Automation"
];

/* ───── Projects (source of truth) ───── */
const PROJECTS = [
    /* Robotics */
    { slug:"autonomous-mobile-robot", title:"Autonomous Mobile Warehouse Robot", category:"robotics", status:"featured", year:2024,
      description:"Graduation Design Project: a fully autonomous mobile robot for warehouse management, developed with the Military Aircrafts Factory, the Arab Organization of Industry, and the Ministry of Scientific Research.",
      techStack:["ROS","LiDAR","Ultrasonic","ARM Cortex-M3","SLAM","Path Planning","C/C++"],
      achievements:["Graduation Design Project (GDP)","Industrial collaboration with 3 government entities","Autonomous navigation with real-time decision making","Integrated heavy-lifting mechanism for pallet handling"],
      detail:"Perception (LiDAR + ultrasonic), decision-making (SLAM + dynamic path planning), and actuation (closed-loop motor control on an ARM MCU) unified in a ROS-based architecture. Demonstrated in a live industrial pilot with three Egyptian government agencies.",
      image:"portfolio_assets/amr.jpg",
      links:{ repository:"https://github.com/mech-zeyadhesham/autonomous-amr" } },

    { slug:"egsa-ground-station", title:"EgSA Ground Station", category:"robotics", status:"featured", year:2024,
      description:"Ground station for the Egyptian Space Agency CanSat-class competition. Custom PCB for telemetry reception, data logging, and live visualization. Team placed 2nd.",
      techStack:["Custom PCB","RF Telemetry","Microcontroller","Ground-station GUI"],
      achievements:["2nd place — Egyptian Space Agency competition","Full custom PCB design from schematic to fabrication","Live telemetry decoding and visualization"],
      detail:"Ground half of a CanSat-class payload system: receive RF telemetry, decode and log packets, and present live data to judges and operators. Disciplined PCB layout, robust framing, and a clean operator interface validated under competition conditions.",
      image:"portfolio_assets/egsa.jpg",
      links:{} },

    { slug:"rov", title:"Remotely Operated Underwater Vehicle", category:"robotics", status:"completed", year:2024,
      description:"Tethered ROV for underwater inspection — 6-DOF thruster control, pressure-sealed electronics, tethered telemetry.",
      techStack:["BLDC Thrusters","ESCs","Tethered Serial","STM32","IMU","PWM Mixing"],
      achievements:["End-to-end mechanical, electrical, and software design","Water-tight enclosure validated under pressure","Stable 6-DOF thruster control via tethered operator console"],
      detail:"Full ROV platform: brushless thrusters for six-degree-of-freedom motion, a pressure-sealed housing, and a tether carrying power and serial telemetry to a surface console. Demonstrated controllable motion with stable depth-hold behavior in pool testing.",
      image:"portfolio_assets/rov.jpg",
      links:{} },

    { slug:"smart-wheelchair", title:"Smart Power Wheelchair", category:"robotics", status:"completed", year:2024,
      description:"Power wheelchair platform with custom motor control and voltage-regulation electronics. Full technical report documenting control circuits and voltage regulation.",
      techStack:["DC Motor Drive","Voltage Regulation","Joystick HMI","SolidWorks","Battery Platform"],
      achievements:["Full mechanical + electrical integration","Detailed technical report on control & voltage-regulation circuits","Battery-powered, user-controlled mobility platform"],
      detail:"Electric wheelchair demonstrating practical assistive mobility. Covered mechanical chassis modeling in SolidWorks, electronic motor drive design, and voltage-regulation circuitry sized for reliable daily use on battery power.",
      image:"portfolio_assets/wheelchair.jpg",
      links:{} },

    { slug:"squash-bot", title:"Squash Training Robot", category:"robotics", status:"archived", year:2023,
      description:"Squash-ball training robot with motorized feed, dual-wheel launcher, and 2-axis aiming. Designed in SolidWorks with printable parts and commercial stepper/DC drivetrain.",
      techStack:["SolidWorks","775 DC Motors","NEMA 17 Steppers","Lead Screws","HTD 3M Belts","3D Printing"],
      achievements:["Complete CAD assembly of launcher, feeder, and aiming frame","Motorized 2-axis aim via lead-screw stages","Ball feed mechanism with printable sub-assembly"],
      detail:"Motorized ball-launcher for solo squash practice. Complete SolidWorks assembly of launcher, gravity-fed hopper, feed mechanism, and 2-axis aiming platform. Project terminated prior to integration — CAD package serves as a reference design.",
      image:"portfolio_assets/squash.jpg",
      links:{} },

    /* Embedded */
    { slug:"daq-module", title:"Data Acquisition (DAQ) Module", category:"embedded", status:"active", year:2025,
      description:"Custom multi-channel data acquisition module — high-resolution analog sampling, digital I/O, and host-side streaming for lab/test-bench instrumentation.",
      techStack:["ARM Cortex-M","Multi-channel ADC","Analog Front-end","USB/UART","Custom PCB"],
      achievements:["Active R&D project","Front-end conditioning + ADC integration in progress","Designed as reusable lab instrumentation"],
      detail:"General-purpose DAQ module as a reusable instrument: multi-channel analog input, digital I/O, and host-side interface for real-time streaming and logging. Analog front-end includes instrumentation amp, anti-aliasing filter, programmable gain. Multi-channel ADC sampled by DMA for continuous throughput.",
      links:{} },

    { slug:"oscilloscope", title:"EMBO Open-Source Oscilloscope", category:"embedded", status:"active", year:2024,
      description:"R&D around the EMBO open-source oscilloscope — a PC-tethered, STM32-based scope with companion Qt desktop application.",
      techStack:["STM32","High-speed ADC","USB","Qt Desktop","Open-source Firmware"],
      achievements:["Studied and adapted EMBO open-source scope platform","Ran the Win64 companion application against firmware targets","Platform for R&D into sampled-signal instrumentation"],
      detail:"Work on the EMBO open-source oscilloscope — STM32 firmware plus a Qt desktop companion — used as a hands-on R&D platform for signal sampling, USB bulk transfer, and oscilloscope UX. Hands-on familiarity with sampled-signal instrumentation end-to-end.",
      links:{ repository:"https://github.com/parezj/EMBO" } },

    { slug:"ev-monitor", title:"Electric Vehicle Power Monitor", category:"embedded", status:"completed", year:2023,
      description:"Custom EV power-system monitoring board. Measures voltage, current, and derived quantities on DC power rails with Arduino-based firmware reporting live values.",
      techStack:["Arduino/AVR","Eagle PCB","V/I Sensing","Serial Telemetry"],
      achievements:["Custom PCB schematic + layout delivered","Functional firmware reporting EV pack telemetry","End-to-end design: sensing → firmware → output"],
      detail:"Purpose-built monitor for an electric-vehicle DC power system: custom PCB plus Arduino firmware sampling voltage and current on the main rails and publishing them as serial telemetry for the vehicle's dashboard and logging stack.",
      image:"portfolio_assets/ev-monitor.jpg",
      links:{} },

    { slug:"motor-driver", title:"30 A H-Bridge Motor Driver", category:"embedded", status:"completed", year:2022,
      description:"Custom high-current H-bridge motor driver PCB up to ~30 A, plus a Cytron-style 10 A half-bridge variant. Includes gate-driver design and test fixture.",
      techStack:["MOSFET H-Bridge","Gate Driver IC","Eagle PCB","High-current Layout","Thermal Management"],
      achievements:["Two complete PCB designs (30 A full-bridge + 10 A half-bridge)","Gate-driver schematic + documentation","Usable on high-torque mobile-robot platforms"],
      detail:"Pair of custom motor-driver boards: a 30 A full H-bridge (MD20A-NEW) for heavier drivetrains, and a 10 A Cytron-style half-bridge clone for lighter applications. Both include proper gate-driver circuitry and layout practices for high-current switching.",
      image:"portfolio_assets/motor-driver.jpg",
      links:{} },

    /* PCB */
    { slug:"32bit-ramps", title:"32-bit RAMPS V0 — 3D Printer Mainboard", category:"pcb", status:"active", year:2025,
      description:"Clean-sheet redesign of the classic RAMPS 3D-printer mainboard on a 32-bit microcontroller platform, running Marlin 2.1.x.",
      techStack:["32-bit ARM","Marlin 2.1.x","Stepper Sockets","Heater MOSFETs","Custom PCB"],
      achievements:["Complete 32-bit RAMPS V0 board design","Marlin 2.1.x configuration tailored to the new board","Modernizes 8-bit RAMPS for higher step rates and better control loops"],
      detail:"Modernized 3D-printer mainboard in the RAMPS tradition — moving from 8-bit AVR to a 32-bit ARM MCU and current Marlin 2.1.x firmware. Higher achievable step rates, better motion planning, headroom for features like linear advance. Build on hold pending fabrication hardware.",
      links:{} },

    { slug:"agro-robot-motherboard", title:"Agricultural Robot Motherboard", category:"pcb", status:"completed", year:2024,
      description:"Custom motherboard PCB for an agricultural robot — microcontroller, motor drivers, sensor interfaces, and power distribution on a single field-ready board.",
      techStack:["MCU","Motor Drivers","Sensor I/O","Power Distribution","Custom PCB"],
      achievements:["Single-board solution for agricultural robot electronics","Reduces wiring complexity vs. modular prototype","Tailored I/O mix for agricultural sensors and actuators"],
      detail:"Custom mainboard for an agricultural robotics platform. Instead of stacking off-the-shelf modules, this design consolidates compute, motor drive interfaces, sensor I/O, and power distribution onto a single PCB tailored to the robot's BOM.",
      image:"portfolio_assets/agro-motherboard.jpg",
      links:{} },

    { slug:"bottle-counter", title:"IoT Bottle Counter Module", category:"pcb", status:"completed", year:2024,
      description:"IoT-enabled bottle counter for industrial/retail lines. Optical/proximity sensing, small PCB, connected firmware stack for upstream reporting.",
      techStack:["IoT Sensor","MCU","Wireless Uplink","Sensor Library","Custom PCB"],
      achievements:["End-to-end sensor + compute + uplink module","Reusable IoT sensor library","Deployable counting node for production/packaging lines"],
      detail:"Small IoT-enabled counting module for bottle-handling lines. Each module pairs a physical sensor with a microcontroller and a wireless uplink so counts can be aggregated centrally instead of read from a local display.",
      image:"portfolio_assets/bottle-counter.jpg",
      links:{} },

    { slug:"tawaf-bracelet", title:"Tawaf Smart Bracelet", category:"pcb", status:"featured", year:2024,
      description:"Wearable smart bracelet supporting pilgrims during Tawaf. OLED display, MPU-9250 IMU, BMP180 barometer, and a Python GUI for serial comms — packaged in a custom 3D-printed watch case.",
      techStack:["Arduino Pro Mini","MPU-9250","BMP180","0.96\" OLED","Python/PyQt","Custom PCB","3D-printed Enclosure"],
      achievements:["Full wearable: PCB + sensors + firmware + enclosure","Python host GUI for live serial communication","Integrated motion + environmental sensing on a small form factor"],
      detail:"Purpose-built wearable to support pilgrims during Tawaf. Combines motion sensing (MPU-9250), environmental sensing (BMP180), and a small on-device OLED display, plus a companion Python GUI for host-side debugging and data capture.",
      image:"portfolio_assets/tawaf.jpg",
      links:{} },

    /* Mechanical */
    { slug:"cornered-desk", title:"Cornered Desk", category:"mechanical", status:"active", year:2024,
      description:"Personal mechanical-design project: a custom corner desk modeled in SolidWorks, exploring furniture-scale ergonomics, material selection, and structural layout.",
      techStack:["SolidWorks","Ergonomic Design","Panel Construction"],
      achievements:["Complete SolidWorks part file (Desk.SLDPRT)","Personal design exploration of ergonomic corner workspace"],
      detail:"Personal SolidWorks project: a custom corner desk sized for a multi-monitor workstation. Focus on getting ergonomic dimensions right (depth, height, monitor distance) before committing to construction materials.",
      links:{} },

    { slug:"mega-amr", title:"Mega AMR — Mobile Robot Platform", category:"mechanical", status:"completed", year:2023,
      description:"Mechanical design of a large-footprint autonomous mobile robot platform. Welded frame, differential drivetrain with 150 mm rubber wheels, Kinect sensor mount, DXF-ready fabrication outputs.",
      techStack:["SolidWorks","150mm Rubber Wheels","DC Gear Motors","Kinect Mount","DXF Exports"],
      achievements:["Full-platform SolidWorks assembly including frame, drivetrain, and sensor mounts","DXF exports for fabrication","STEP exports for external review"],
      detail:"Mechanical design of a large AMR platform — the 'heavy' class of the mobile-robot work. SolidWorks package includes frame, drivetrain (motors, brackets, wheels), sensor mounts (Kinect), and ancillary mechanisms, plus DXF exports ready for sheet-metal/laser fabrication.",
      image:"portfolio_assets/mega-amr.jpg",
      links:{} },

    { slug:"mine-ugv", title:"Mine Inspection UGV", category:"mechanical", status:"featured", year:2024,
      description:"UGV for mine inspection — integrated robotic arm, gripper, and gear-and-chain drivetrain. Multiple design revisions (V1 → V2) with standalone sub-assemblies.",
      techStack:["SolidWorks","Gear & Chain","Multi-DOF Arm","Gripper","CAD Revisions"],
      achievements:["Complete mobile platform with integrated manipulation arm","Gear-and-chain drivetrain for rough-terrain capability","Iterative design — V1 through V2 with captured lessons"],
      detail:"Mechanical design of a UGV intended for mine inspection — mobile platform with onboard manipulation (arm + gripper) capable of traversing uneven terrain. Multiple revisions (OLD-UGV → UGV → UGV V2) with standalone sub-assemblies for the ARM, GRIPPER, and gear-and-chain drivetrain.",
      image:"portfolio_assets/mine-ugv.jpg",
      links:{} },

    /* Software */
    { slug:"agricultural-monitoring", title:"Agricultural Monitoring System", category:"software", status:"completed", year:2024,
      description:"Software layer for an agricultural monitoring system — reads environmental and soil sensors from the field, aggregates data, and surfaces it through a monitoring interface.",
      techStack:["Embedded Firmware","Serial/Wireless","Data Aggregation","Python Dashboard"],
      achievements:["Field-to-dashboard software pipeline","Works with the Agricultural Robot Motherboard"],
      detail:"Software counterpart to the agricultural-robotics hardware work: firmware on sensing nodes, a transport path to a host machine, and host-side tooling for viewing and exporting data. Forms the software layer of a complete field-robotics stack.",
      links:{} },

    { slug:"rc-car-control", title:"RC Car Control Software", category:"software", status:"completed", year:2024,
      description:"Control-software stack for a remote-controlled car — operator input, command encoding, wireless transport, and on-vehicle motor control.",
      techStack:["MCU Firmware","Wireless Link","PWM Control","Operator Input"],
      achievements:["End-to-end teleop stack: operator → wireless → vehicle actuation","Smooth steering / throttle response via PWM control"],
      detail:"Software for an RC car covering both ends of the link: operator-side transmitter that encodes joystick inputs, and the vehicle-side receiver that decodes them and drives steering servo and drive motor. Responsive manual control — a foundation for layering autonomy on top of a trusted teleop link.",
      links:{} },

    { slug:"esp32-projects", title:"ESP32 Projects", category:"software", status:"active", year:2024,
      description:"Collection of ESP32-based firmware experiments — Wi-Fi/BLE connectivity, sensor interfacing, and small host-side PyQt GUIs for interacting with devices over serial.",
      techStack:["ESP32","Wi-Fi/BLE","Arduino/ESP-IDF","PyQt","Qt Designer"],
      achievements:["Multiple firmware experiments on ESP32 targets","Custom PyQt GUIs (QT.py, gui.py, untitled.ui)","End-to-end workflow: device firmware + desktop tooling"],
      detail:"Collection of ESP32 experiments plus desktop tooling: small PyQt GUIs for talking to devices over serial and visualizing sensor streams. A reusable template stack — ESP32 firmware on one side, PyQt tool on the other — that accelerates future IoT and robotics experiments.",
      links:{} },

    /* R&D */
    { slug:"kuka-robot-cv", title:"KUKA Robot Computer Vision Integration", category:"research", status:"featured", year:2025,
      description:"R&D integrating computer-vision perception with a KUKA industrial manipulator — object detection and pose estimation feeding pick-and-place and alignment tasks.",
      techStack:["KUKA Robot","OpenCV","Python","Camera Calibration","Hand-Eye Calibration","KRL"],
      achievements:["Vision-guided robot motion on an industrial platform","Hand-eye calibration for camera ↔ robot frame alignment","Repeatable integration pattern for CV + industrial robot"],
      detail:"R&D on coupling a computer-vision pipeline to a KUKA industrial robot so the arm can react to what it sees — part detection, pose estimation, and on-the-fly motion commands in place of fixed hard-coded poses. A reusable pattern for vision-guided industrial manipulation.",
      links:{} },

    { slug:"kuka-digital-twin", title:"KUKA Robot Digital Twin", category:"research", status:"featured", year:2025,
      description:"Digital-twin research around a KUKA industrial robot — virtualizing the cell so programs, trajectories, and safety logic can be validated offline before running on real hardware.",
      techStack:["KUKA.Sim","3D Cell Model","Trajectory Validation","Offline Programming"],
      achievements:["Virtual cell mirroring the physical KUKA setup","Offline trajectory validation before touching real hardware","Platform for collision / reach / cycle-time studies"],
      detail:"Digital-twin workstream letting the KUKA cell be reasoned about in software: geometry, kinematics, and programs in sync with the physical setup so changes can be validated before they're committed to real-world motion. Includes collision checks, reach analysis, cycle-time estimation, safety-envelope verification.",
      links:{} },

    { slug:"safety-cell-guarding", title:"Safety Cell Guarding Research", category:"research", status:"active", year:2025,
      description:"Research into safety-guarding strategies for industrial robot cells — physical guarding, safety-rated sensors (light curtains, scanners), and safe-motion logic for human-robot coexistence.",
      techStack:["Safety-rated Sensors","Safety PLC","ISO 10218","ISO/TS 15066"],
      achievements:["Survey of safety-guarding strategies for robot cells","Mapped hardware, software, and procedural layers of cell safety"],
      detail:"R&D study of how robot cells are kept safe in practice: physical guards, safety-rated sensors, safety PLCs driving safe-stop logic, and the procedural/standards layer on top. A consolidated view that can inform future cell design, including collaborative-robot deployments.",
      links:{} },

    { slug:"aruco-jig-improvement", title:"ArUco Marker Jig Improvement", category:"research", status:"active", year:2025,
      description:"R&D improving an ArUco-marker-based jig for robot pose estimation / hand-eye calibration — reducing error and improving repeatability of vision-guided robot tasks.",
      techStack:["ArUco + OpenCV","Hand-Eye Calibration","Custom Fixture","Error Analysis"],
      achievements:["Improved-accuracy ArUco-based calibration jig","Reduced pose-estimation error vs. original jig","Reusable calibration workflow for future vision-guided projects"],
      detail:"Focused improvement work on an ArUco-marker jig used for robot calibration and pose estimation. Goal: smaller residual error and better run-to-run repeatability when the jig is used to tie a camera frame to a robot TCP. Metrology-grade thinking about vision systems and their error sources.",
      links:{} },

    { slug:"palletizing-robot", title:"Palletizing Robot Research", category:"research", status:"featured", year:2025,
      description:"R&D on a palletizing robot cell — pattern generation, motion planning, and integration with in/out conveyor logic to turn a manipulator into a production-grade palletizer.",
      techStack:["Industrial Manipulator","Pattern Generation","Motion Planning","PLC Integration","End-effector Design"],
      achievements:["End-to-end palletizing workflow on an industrial robot","Pattern generation for mixed carton sizes","Cycle-time-aware motion planning"],
      detail:"Research on turning a general industrial manipulator into a palletizing cell: computing valid stacking patterns, planning pick-and-place motion, and synchronizing with conveyor and PLC logic so the cell can run end-to-end. Full-stack industrial robotics — planning, manipulation, plant-floor integration.",
      links:{} }
];

const statusConfig = {
    featured:  { label: "Featured",  class: "status-featured" },
    active:    { label: "Active",    class: "status-active" },
    completed: { label: "Completed", class: "status-completed" },
    archived:  { label: "Archived",  class: "status-archived" }
};

const categoryEmojis = {
    robotics: "🤖", embedded: "💻", pcb: "⚡",
    mechanical: "⚙️", software: "🔧", research: "🔬"
};
const categoryNames = {
    robotics: "Robotics", embedded: "Embedded", pcb: "PCB",
    mechanical: "Mechanical", software: "Software", research: "R&D"
};

const getCategoryEmoji = c => categoryEmojis[c] || "🔧";
const getCategoryName  = c => categoryNames[c]  || c;
