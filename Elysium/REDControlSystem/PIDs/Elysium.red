{
  "name": "Elysium",
  "version": "2.0.0",
  "components": [
    {
      "id": "TK_1",
      "type": "tank",
      "label": "N20",
      "hardware": {},
      "extras": {},
      "rotation": 0,
      "hide_lbl": false
    },
    {
      "id": "TK_2",
      "type": "tank",
      "label": "Fill N20",
      "hardware": {},
      "extras": {},
      "rotation": 0,
      "hide_lbl": false
    },
    {
      "id": "TK_3",
      "type": "tank",
      "label": "Fill N2O",
      "hardware": {},
      "extras": {},
      "rotation": 0,
      "hide_lbl": false
    },
    {
      "id": "TK_4",
      "type": "tank",
      "label": "Fuel Fill",
      "hardware": {},
      "extras": {},
      "rotation": 0,
      "hide_lbl": false
    },
    {
      "id": "BV_1",
      "type": "ball_valve",
      "label": " ",
      "hardware": {
        "relay": 99
      },
      "extras": {},
      "rotation": 90,
      "hide_lbl": false
    },
    {
      "id": "CV_1",
      "type": "check_valve",
      "label": " ",
      "hardware": {},
      "extras": {},
      "rotation": 0,
      "hide_lbl": false
    },
    {
      "id": "GV_1",
      "type": "globe_valve",
      "label": "GV-1",
      "hardware": {
        "relay": 32
      },
      "extras": {},
      "rotation": 90,
      "hide_lbl": true
    },
    {
      "id": "PT_1",
      "type": "pressure",
      "label": "P1",
      "hardware": {
        "adc": 1
      },
      "extras": {
        "thresholds": {
          "mawp": null,
          "mawp_action": "abort",
          "mawp_target": "",
          "mawp_close_below": null,
          "meop": null,
          "meop_action": "open_valve",
          "meop_target": "",
          "meop_close_below": null,
          "relief": null,
          "relief_action": "open_valve",
          "relief_target": "",
          "relief_close_below": null,
          "soak_ms": 0
        }
      },
      "rotation": 0,
      "hide_lbl": false
    },
    {
      "id": "PT_2",
      "type": "pressure",
      "label": "P2",
      "hardware": {
        "adc": 2
      },
      "extras": {
        "thresholds": {
          "mawp": null,
          "mawp_action": "abort",
          "mawp_target": "",
          "mawp_close_below": null,
          "meop": null,
          "meop_action": "open_valve",
          "meop_target": "",
          "meop_close_below": null,
          "relief": null,
          "relief_action": "open_valve",
          "relief_target": "",
          "relief_close_below": null,
          "soak_ms": 0
        }
      },
      "rotation": 0,
      "hide_lbl": false
    },
    {
      "id": "PT_3",
      "type": "pressure",
      "label": "P3",
      "hardware": {
        "adc": 3
      },
      "extras": {
        "thresholds": {
          "mawp": null,
          "mawp_action": "abort",
          "mawp_target": "",
          "mawp_close_below": null,
          "meop": null,
          "meop_action": "open_valve",
          "meop_target": "",
          "meop_close_below": null,
          "relief": null,
          "relief_action": "open_valve",
          "relief_target": "",
          "relief_close_below": null,
          "soak_ms": 0
        }
      },
      "rotation": 0,
      "hide_lbl": false
    },
    {
      "id": "LAB_1",
      "type": "label",
      "label": "INJ",
      "hardware": {},
      "extras": {},
      "rotation": 0,
      "hide_lbl": false
    },
    {
      "id": "PT_4",
      "type": "pressure",
      "label": "P4",
      "hardware": {
        "adc": 4
      },
      "extras": {
        "thresholds": {
          "mawp": null,
          "mawp_action": "abort",
          "mawp_target": "",
          "mawp_close_below": null,
          "meop": null,
          "meop_action": "open_valve",
          "meop_target": "",
          "meop_close_below": null,
          "relief": null,
          "relief_action": "open_valve",
          "relief_target": "",
          "relief_close_below": null,
          "soak_ms": 0
        }
      },
      "rotation": 0,
      "hide_lbl": true
    },
    {
      "id": "TK_5",
      "type": "tank",
      "label": "Fill GN2",
      "hardware": {},
      "extras": {},
      "rotation": 0,
      "hide_lbl": false
    },
    {
      "id": "BV_2",
      "type": "ball_valve",
      "label": " ",
      "hardware": {
        "relay": 99
      },
      "extras": {},
      "rotation": 90,
      "hide_lbl": false
    },
    {
      "id": "REG_1",
      "type": "regulator",
      "label": " ",
      "hardware": {},
      "extras": {},
      "rotation": 180,
      "hide_lbl": false
    },
    {
      "id": "PT_5",
      "type": "pressure",
      "label": "P5",
      "hardware": {
        "adc": 5
      },
      "extras": {
        "thresholds": {
          "mawp": null,
          "mawp_action": "abort",
          "mawp_target": "",
          "mawp_close_below": null,
          "meop": null,
          "meop_action": "open_valve",
          "meop_target": "",
          "meop_close_below": null,
          "relief": null,
          "relief_action": "open_valve",
          "relief_target": "",
          "relief_close_below": null,
          "soak_ms": 0
        }
      },
      "rotation": 0,
      "hide_lbl": false
    },
    {
      "id": "VAL_1",
      "type": "valve",
      "label": "NCS1",
      "hardware": {
        "relay": 1
      },
      "extras": {},
      "rotation": 90,
      "hide_lbl": false
    },
    {
      "id": "CV_2",
      "type": "check_valve",
      "label": " ",
      "hardware": {},
      "extras": {},
      "rotation": 180,
      "hide_lbl": false
    },
    {
      "id": "PRV_1",
      "type": "prv",
      "label": " ",
      "hardware": {},
      "extras": {},
      "rotation": 0,
      "hide_lbl": false
    },
    {
      "id": "PSV_1",
      "type": "psv",
      "label": " ",
      "hardware": {},
      "extras": {},
      "rotation": 0,
      "hide_lbl": false
    },
    {
      "id": "VAL_2",
      "type": "valve",
      "label": "NCS2",
      "hardware": {
        "relay": 2
      },
      "extras": {},
      "rotation": 0,
      "hide_lbl": false
    },
    {
      "id": "VAL_3",
      "type": "valve",
      "label": "NCS3",
      "hardware": {
        "relay": 3
      },
      "extras": {},
      "rotation": 180,
      "hide_lbl": true
    },
    {
      "id": "LAB_2",
      "type": "label",
      "label": "Fill Valve",
      "hardware": {},
      "extras": {},
      "rotation": 0,
      "hide_lbl": false
    },
    {
      "id": "LAB_3",
      "type": "label",
      "label": "NCS5",
      "hardware": {},
      "extras": {},
      "rotation": 0,
      "hide_lbl": false
    },
    {
      "id": "LAB_4",
      "type": "label",
      "label": "NCS6",
      "hardware": {},
      "extras": {},
      "rotation": 0,
      "hide_lbl": false
    },
    {
      "id": "VAL_4",
      "type": "valve",
      "label": "NCS4",
      "hardware": {
        "relay": 4
      },
      "extras": {},
      "rotation": 180,
      "hide_lbl": false
    },
    {
      "id": "VAL_5",
      "type": "valve",
      "label": "NCS5",
      "hardware": {
        "relay": 5,
        "adc": 5
      },
      "extras": {},
      "rotation": 90,
      "hide_lbl": true
    },
    {
      "id": "VAL_6",
      "type": "valve",
      "label": "NCS6",
      "hardware": {
        "relay": 6,
        "adc": 6
      },
      "extras": {},
      "rotation": 0,
      "hide_lbl": true
    },
    {
      "id": "LAB_5",
      "type": "label",
      "label": "GV-1",
      "hardware": {},
      "extras": {},
      "rotation": 0,
      "hide_lbl": false
    },
    {
      "id": "LAB_6",
      "type": "label",
      "label": "NCS3",
      "hardware": {},
      "extras": {},
      "rotation": 0,
      "hide_lbl": false
    },
    {
      "id": "BV_3",
      "type": "ball_valve",
      "label": "LA-BV1",
      "hardware": {
        "relay": 16
      },
      "extras": {},
      "rotation": 90,
      "hide_lbl": true
    },
    {
      "id": "LAB_7",
      "type": "label",
      "label": "LA-BV1",
      "hardware": {},
      "extras": {},
      "rotation": 0,
      "hide_lbl": false
    },
    {
      "id": "LAB_8",
      "type": "label",
      "label": "P8",
      "hardware": {},
      "extras": {},
      "rotation": 0,
      "hide_lbl": false
    },
    {
      "id": "PT_6",
      "type": "pressure",
      "label": "P6",
      "hardware": {
        "adc": 6
      },
      "extras": {
        "thresholds": {
          "mawp": null,
          "mawp_action": "abort",
          "mawp_target": "",
          "mawp_close_below": null,
          "meop": null,
          "meop_action": "open_valve",
          "meop_target": "",
          "meop_close_below": null,
          "relief": null,
          "relief_action": "open_valve",
          "relief_target": "",
          "relief_close_below": null,
          "soak_ms": 0
        }
      },
      "rotation": 0,
      "hide_lbl": false
    },
    {
      "id": "GV_2",
      "type": "globe_valve",
      "label": "GV-2",
      "hardware": {
        "relay": 33
      },
      "extras": {},
      "rotation": 90,
      "hide_lbl": true
    },
    {
      "id": "LAB_9",
      "type": "label",
      "label": "GV-2",
      "hardware": {},
      "extras": {},
      "rotation": 0,
      "hide_lbl": false
    },
    {
      "id": "PT_7",
      "type": "pressure",
      "label": "P7",
      "hardware": {
        "adc": 7
      },
      "extras": {
        "thresholds": {
          "mawp": null,
          "mawp_action": "abort",
          "mawp_target": "",
          "mawp_close_below": null,
          "meop": null,
          "meop_action": "open_valve",
          "meop_target": "",
          "meop_close_below": null,
          "relief": null,
          "relief_action": "open_valve",
          "relief_target": "",
          "relief_close_below": null,
          "soak_ms": 0
        }
      },
      "rotation": 0,
      "hide_lbl": false
    },
    {
      "id": "PT_8",
      "type": "pressure",
      "label": "P8",
      "hardware": {
        "adc": 8
      },
      "extras": {
        "thresholds": {
          "mawp": null,
          "mawp_action": "abort",
          "mawp_target": "",
          "mawp_close_below": null,
          "meop": null,
          "meop_action": "open_valve",
          "meop_target": "",
          "meop_close_below": null,
          "relief": null,
          "relief_action": "open_valve",
          "relief_target": "",
          "relief_close_below": null,
          "soak_ms": 0
        }
      },
      "rotation": 0,
      "hide_lbl": true
    },
    {
      "id": "LAB_10",
      "type": "label",
      "label": "P6",
      "hardware": {},
      "extras": {},
      "rotation": 0,
      "hide_lbl": false
    },
    {
      "id": "LAB_11",
      "type": "label",
      "label": "P4",
      "hardware": {},
      "extras": {},
      "rotation": 0,
      "hide_lbl": false
    },
    {
      "id": "CV_3",
      "type": "check_valve",
      "label": " ",
      "hardware": {},
      "extras": {},
      "rotation": 90,
      "hide_lbl": false
    },
    {
      "id": "LOA_1",
      "type": "load_cell",
      "label": "LC1",
      "hardware": {
        "adc": 12
      },
      "extras": {},
      "rotation": 0,
      "hide_lbl": false
    },
    {
      "id": "LOA_2",
      "type": "load_cell",
      "label": "LC2",
      "hardware": {
        "adc": 13
      },
      "extras": {},
      "rotation": 0,
      "hide_lbl": false
    },
    {
      "id": "LOA_3",
      "type": "load_cell",
      "label": "LC3",
      "hardware": {
        "adc": 14
      },
      "extras": {},
      "rotation": 0,
      "hide_lbl": false
    },
    {
      "id": "TC_1",
      "type": "temperature",
      "label": "TC1",
      "hardware": {
        "adc": 9
      },
      "extras": {},
      "rotation": 0,
      "hide_lbl": false
    },
    {
      "id": "TC_2",
      "type": "temperature",
      "label": "TC_2",
      "hardware": {
        "adc": 10
      },
      "extras": {},
      "rotation": 0,
      "hide_lbl": false
    },
    {
      "id": "TC_3",
      "type": "temperature",
      "label": "TC_3",
      "hardware": {
        "adc": 11
      },
      "extras": {},
      "rotation": 0,
      "hide_lbl": false
    }
  ],
  "connections": [],
  "layout": {
    "TK_1": {
      "x": 640.0,
      "y": 240.0
    },
    "TK_2": {
      "x": 200.0,
      "y": 480.0
    },
    "TK_3": {
      "x": 280.0,
      "y": 480.0
    },
    "TK_4": {
      "x": 480.0,
      "y": 240.0
    },
    "BV_1": {
      "x": 480.0,
      "y": 160.0
    },
    "CV_1": {
      "x": 600.0,
      "y": 360.0
    },
    "GV_1": {
      "x": 640.0,
      "y": 460.0
    },
    "PT_1": {
      "x": 1050.0,
      "y": 490.0
    },
    "PT_2": {
      "x": 540.0,
      "y": 320.0
    },
    "PT_3": {
      "x": 590.0,
      "y": 410.0
    },
    "LAB_1": {
      "x": 640.0,
      "y": 570.0
    },
    "PT_4": {
      "x": 710.0,
      "y": 410.0
    },
    "TK_5": {
      "x": 1000.0,
      "y": 670.0
    },
    "BV_2": {
      "x": 1000.0,
      "y": 590.0
    },
    "REG_1": {
      "x": 1000.0,
      "y": 550.0
    },
    "PT_5": {
      "x": 590.0,
      "y": 520.0
    },
    "VAL_1": {
      "x": 1000,
      "y": 440
    },
    "CV_2": {
      "x": 960.0,
      "y": 360.0
    },
    "PRV_1": {
      "x": 880.0,
      "y": 330.0
    },
    "PSV_1": {
      "x": 890.0,
      "y": 390.0
    },
    "VAL_2": {
      "x": 360.0,
      "y": 360.0
    },
    "VAL_3": {
      "x": 850.0,
      "y": 330.0
    },
    "LAB_2": {
      "x": 440.0,
      "y": 130.0
    },
    "LAB_3": {
      "x": 690.0,
      "y": 50.0
    },
    "LAB_4": {
      "x": 690.0,
      "y": -30.0
    },
    "VAL_4": {
      "x": 850.0,
      "y": 390.0
    },
    "VAL_5": {
      "x": 640.0,
      "y": 80.0
    },
    "VAL_6": {
      "x": 640.0,
      "y": 0.0
    },
    "LAB_5": {
      "x": 610.0,
      "y": 430.0
    },
    "LAB_6": {
      "x": 850.0,
      "y": 270.0
    },
    "BV_3": {
      "x": 710.0,
      "y": 220.0
    },
    "LAB_7": {
      "x": 760.0,
      "y": 190.0
    },
    "LAB_8": {
      "x": 550.0,
      "y": 550.0
    },
    "PT_6": {
      "x": 710.0,
      "y": 510.0
    },
    "GV_2": {
      "x": 710.0,
      "y": 460.0
    },
    "LAB_9": {
      "x": 750.0,
      "y": 430.0
    },
    "PT_7": {
      "x": 750.0,
      "y": 630.0
    },
    "PT_8": {
      "x": 580.0,
      "y": 580.0
    },
    "LAB_10": {
      "x": 750.0,
      "y": 480.0
    },
    "LAB_11": {
      "x": 750.0,
      "y": 380.0
    },
    "CV_3": {
      "x": 710.0,
      "y": 560.0
    },
    "LOA_1": {
      "x": 240.0,
      "y": 650.0
    },
    "LOA_2": {
      "x": 240.0,
      "y": 710.0
    },
    "LOA_3": {
      "x": 240.0,
      "y": 770.0
    },
    "TC_1": {
      "x": 80.0,
      "y": 650.0
    },
    "TC_2": {
      "x": 80.0,
      "y": 710.0
    },
    "TC_3": {
      "x": 80.0,
      "y": 770.0
    }
  },
  "lines": [
    {
      "id": "line_0",
      "points": [
        {
          "x": 200.0,
          "y": 440.0
        },
        {
          "x": 200.0,
          "y": 360.0
        },
        {
          "x": 360.0,
          "y": 360.0
        },
        {
          "x": 360.0,
          "y": 360.0
        }
      ],
      "fluid": "generic",
      "connects": [],
      "dotted": false
    },
    {
      "id": "line_1",
      "points": [
        {
          "x": 280.0,
          "y": 440.0
        },
        {
          "x": 280.0,
          "y": 360.0
        },
        {
          "x": 360.0,
          "y": 360.0
        }
      ],
      "fluid": "generic",
      "connects": [],
      "dotted": false
    },
    {
      "id": "line_3",
      "points": [
        {
          "x": 640.0,
          "y": 360.0
        },
        {
          "x": 640.0,
          "y": 460.0
        },
        {
          "x": 640.0,
          "y": 410.0
        },
        {
          "x": 600.0,
          "y": 410.0
        },
        {
          "x": 640.0,
          "y": 410.0
        },
        {
          "x": 640.0,
          "y": 520.0
        },
        {
          "x": 600.0,
          "y": 520.0
        },
        {
          "x": 640.0,
          "y": 520.0
        },
        {
          "x": 640.0,
          "y": 580.0
        },
        {
          "x": 610.0,
          "y": 580.0
        },
        {
          "x": 610.0,
          "y": 610.0
        },
        {
          "x": 610.0,
          "y": 580.0
        },
        {
          "x": 670.0,
          "y": 580.0
        },
        {
          "x": 670.0,
          "y": 610.0
        },
        {
          "x": 710.0,
          "y": 610.0
        },
        {
          "x": 570.0,
          "y": 610.0
        },
        {
          "x": 570.0,
          "y": 650.0
        },
        {
          "x": 710.0,
          "y": 650.0
        },
        {
          "x": 710.0,
          "y": 610.0
        },
        {
          "x": 710.0,
          "y": 650.0
        },
        {
          "x": 680.0,
          "y": 720.0
        },
        {
          "x": 600.0,
          "y": 720.0
        },
        {
          "x": 570.0,
          "y": 650.0
        }
      ],
      "fluid": "generic",
      "connects": [],
      "dotted": false
    },
    {
      "id": "line_4",
      "points": [
        {
          "x": 600.0,
          "y": 720.0
        },
        {
          "x": 560.0,
          "y": 910.0
        },
        {
          "x": 720.0,
          "y": 910.0
        },
        {
          "x": 680.0,
          "y": 720.0
        }
      ],
      "fluid": "generic",
      "connects": [],
      "dotted": false
    },
    {
      "id": "line_5",
      "points": [
        {
          "x": 580.0,
          "y": 580.0
        },
        {
          "x": 580.0,
          "y": 610.0
        }
      ],
      "fluid": "generic",
      "connects": [],
      "dotted": false
    },
    {
      "id": "line_6",
      "points": [
        {
          "x": 540.0,
          "y": 330.0
        },
        {
          "x": 540.0,
          "y": 360.0
        }
      ],
      "fluid": "generic",
      "connects": [],
      "dotted": false
    },
    {
      "id": "line_8",
      "points": [
        {
          "x": 710.0,
          "y": 630.0
        },
        {
          "x": 740.0,
          "y": 630.0
        }
      ],
      "fluid": "generic",
      "connects": [],
      "dotted": false
    },
    {
      "id": "line_10",
      "points": [
        {
          "x": 620.0,
          "y": 360.0
        },
        {
          "x": 640.0,
          "y": 360.0
        },
        {
          "x": 640.0,
          "y": 250.0
        }
      ],
      "fluid": "generic",
      "connects": [],
      "dotted": false
    },
    {
      "id": "line_11",
      "points": [
        {
          "x": 640.0,
          "y": 170.0
        },
        {
          "x": 640.0,
          "y": 230.0
        }
      ],
      "fluid": "generic",
      "connects": [],
      "dotted": false
    },
    {
      "id": "line_11",
      "points": [
        {
          "x": 360.0,
          "y": 360.0
        },
        {
          "x": 580.0,
          "y": 360.0
        }
      ],
      "fluid": "generic",
      "connects": [],
      "dotted": false
    },
    {
      "id": "line_11",
      "points": [
        {
          "x": 480.0,
          "y": 240.0
        },
        {
          "x": 480.0,
          "y": 160.0
        },
        {
          "x": 480.0,
          "y": 40.0
        },
        {
          "x": 640.0,
          "y": 40.0
        },
        {
          "x": 640.0,
          "y": 0.0
        },
        {
          "x": 640.0,
          "y": 80.0
        },
        {
          "x": 640.0,
          "y": 240.0
        }
      ],
      "fluid": "generic",
      "connects": [],
      "dotted": false
    },
    {
      "id": "line_12",
      "points": [
        {
          "x": 640.0,
          "y": 160.0
        },
        {
          "x": 710.0,
          "y": 160.0
        },
        {
          "x": 710.0,
          "y": 220.0
        },
        {
          "x": 710.0,
          "y": 420.0
        },
        {
          "x": 710.0,
          "y": 460.0
        },
        {
          "x": 710.0,
          "y": 510.0
        },
        {
          "x": 710.0,
          "y": 540.0
        }
      ],
      "fluid": "generic",
      "connects": [],
      "dotted": true
    },
    {
      "id": "line_13",
      "points": [
        {
          "x": 640.0,
          "y": 610.0
        },
        {
          "x": 710.0,
          "y": 580.0
        }
      ],
      "fluid": "generic",
      "connects": [],
      "dotted": true
    },
    {
      "id": "line_13",
      "points": [
        {
          "x": 650.0,
          "y": 250.0
        },
        {
          "x": 650.0,
          "y": 360.0
        },
        {
          "x": 850.0,
          "y": 360.0
        },
        {
          "x": 850.0,
          "y": 330.0
        },
        {
          "x": 850.0,
          "y": 390.0
        },
        {
          "x": 850.0,
          "y": 360.0
        },
        {
          "x": 940.0,
          "y": 360.0
        }
      ],
      "fluid": "generic",
      "connects": [],
      "dotted": false
    },
    {
      "id": "line_14",
      "points": [
        {
          "x": 1000.0,
          "y": 650.0
        },
        {
          "x": 1000.0,
          "y": 590.0
        },
        {
          "x": 1000.0,
          "y": 560.0
        },
        {
          "x": 1000.0,
          "y": 490.0
        },
        {
          "x": 1040.0,
          "y": 490.0
        },
        {
          "x": 1000.0,
          "y": 490.0
        },
        {
          "x": 1000.0,
          "y": 440.0
        },
        {
          "x": 1000.0,
          "y": 360.0
        },
        {
          "x": 980.0,
          "y": 360.0
        }
      ],
      "fluid": "generic",
      "connects": [],
      "dotted": false
    }
  ],
  "parameters": {
    "tank_volume": 0.0,
    "notes": ""
  },
  "rules": [
    {
      "id": "logic_rule_1",
      "condition_type": "expression",
      "action": "abort",
      "enabled": true,
      "sensor_id": "",
      "expression": "P8 > 700",
      "description": "high chamber pressure",
      "target_valve": "",
      "close_valve_below": null,
      "soak_ms": 0
    },
    {
      "id": "logic_rule_2",
      "condition_type": "expression",
      "action": "abort",
      "enabled": true,
      "sensor_id": "",
      "expression": "P8 > P7",
      "description": "reverse flow",
      "target_valve": "",
      "close_valve_below": null,
      "soak_ms": 0
    },
    {
      "id": "logic_rule_3",
      "condition_type": "expression",
      "action": "abort",
      "enabled": true,
      "sensor_id": "",
      "expression": "P5 - P3 >= 5",
      "description": "high upstream pressure",
      "target_valve": "",
      "close_valve_below": null,
      "soak_ms": 150
    },
    {
      "id": "logic_rule_4",
      "condition_type": "expression",
      "action": "abort",
      "enabled": true,
      "sensor_id": "",
      "expression": "P6 - P4 >= 5",
      "description": "high upstream pressure",
      "target_valve": "",
      "close_valve_below": null,
      "soak_ms": 150
    },
    {
      "id": "logic_rule_5",
      "condition_type": "expression",
      "action": "open_valve",
      "enabled": true,
      "sensor_id": "",
      "expression": "P2 > 1375",
      "description": "high p2",
      "target_valve": "NCS3",
      "close_valve_below": 1250.0,
      "soak_ms": 0
    },
    {
      "id": "logic_rule_6",
      "condition_type": "expression",
      "action": "warn",
      "enabled": true,
      "sensor_id": "",
      "expression": "P2 > 1375",
      "description": "Warning: P2 > 1375. Opening NCS3...",
      "target_valve": "",
      "close_valve_below": null,
      "soak_ms": 0
    }
  ],
  "sequence": [
    {
      "name": "Pressurization",
      "time_offset": 0.0,
      "open_valves": []
    },
    {
      "name": "Fire",
      "time_offset": 5.0,
      "open_valves": [
        "GV_1",
        "GV_2",
        "BV_3",
        "VAL_1"
      ]
    },
    {
      "name": "Kill and Vent",
      "time_offset": 20.0,
      "open_valves": [
        "VAL_3",
        "BV_3",
        "GV_1",
        "GV_2"
      ]
    }
  ]
}