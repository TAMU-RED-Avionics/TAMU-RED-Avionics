{
  "name": "Elysium",
  "version": "2.0.0",
  "components": [
    {
      "id": "TK_1",
      "type": "tank",
      "label": "N20",
      "hardware": {},
      "extras": {
        "scale_y": 2.0
      },
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
          "mawp_message": "",
          "mawp_target": "",
          "mawp_close_below": null,
          "meop": null,
          "meop_action": "open_valve",
          "meop_message": "",
          "meop_target": "",
          "meop_close_below": null,
          "relief": null,
          "relief_action": "open_valve",
          "relief_message": "",
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
          "mawp_message": "",
          "mawp_target": "",
          "mawp_close_below": null,
          "meop": null,
          "meop_action": "open_valve",
          "meop_message": "",
          "meop_target": "",
          "meop_close_below": null,
          "relief": null,
          "relief_action": "open_valve",
          "relief_message": "",
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
          "mawp_message": "",
          "mawp_target": "",
          "mawp_close_below": null,
          "meop": null,
          "meop_action": "open_valve",
          "meop_message": "",
          "meop_target": "",
          "meop_close_below": null,
          "relief": null,
          "relief_action": "open_valve",
          "relief_message": "",
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
          "mawp_message": "",
          "mawp_target": "",
          "mawp_close_below": null,
          "meop": null,
          "meop_action": "open_valve",
          "meop_message": "",
          "meop_target": "",
          "meop_close_below": null,
          "relief": null,
          "relief_action": "open_valve",
          "relief_message": "",
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
          "mawp_message": "",
          "mawp_target": "",
          "mawp_close_below": null,
          "meop": null,
          "meop_action": "open_valve",
          "meop_message": "",
          "meop_target": "",
          "meop_close_below": null,
          "relief": null,
          "relief_action": "open_valve",
          "relief_message": "",
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
          "mawp_message": "",
          "mawp_target": "",
          "mawp_close_below": null,
          "meop": null,
          "meop_action": "open_valve",
          "meop_message": "",
          "meop_target": "",
          "meop_close_below": null,
          "relief": null,
          "relief_action": "open_valve",
          "relief_message": "",
          "relief_target": "",
          "relief_close_below": null,
          "soak_ms": 0
        }
      },
      "rotation": 0,
      "hide_lbl": true
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
          "mawp_message": "",
          "mawp_target": "",
          "mawp_close_below": null,
          "meop": null,
          "meop_action": "open_valve",
          "meop_message": "",
          "meop_target": "",
          "meop_close_below": null,
          "relief": null,
          "relief_action": "open_valve",
          "relief_message": "",
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
          "mawp_message": "",
          "mawp_target": "",
          "mawp_close_below": null,
          "meop": null,
          "meop_action": "open_valve",
          "meop_message": "",
          "meop_target": "",
          "meop_close_below": null,
          "relief": null,
          "relief_action": "open_valve",
          "relief_message": "",
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
      "extras": {
        "thresholds": {
          "mawp": null,
          "mawp_action": "abort",
          "mawp_message": "",
          "mawp_target": "",
          "mawp_close_below": null,
          "meop": null,
          "meop_action": "open_valve",
          "meop_message": "",
          "meop_target": "",
          "meop_close_below": null,
          "relief": null,
          "relief_action": "open_valve",
          "relief_message": "",
          "relief_target": "",
          "relief_close_below": null,
          "soak_ms": 0
        }
      },
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
      "extras": {
        "thresholds": {
          "mawp": null,
          "mawp_action": "abort",
          "mawp_message": "",
          "mawp_target": "",
          "mawp_close_below": null,
          "meop": null,
          "meop_action": "open_valve",
          "meop_message": "",
          "meop_target": "",
          "meop_close_below": null,
          "relief": null,
          "relief_action": "open_valve",
          "relief_message": "",
          "relief_target": "",
          "relief_close_below": null,
          "soak_ms": 0
        }
      },
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
      "extras": {
        "thresholds": {
          "mawp": null,
          "mawp_action": "abort",
          "mawp_message": "",
          "mawp_target": "",
          "mawp_close_below": null,
          "meop": null,
          "meop_action": "open_valve",
          "meop_message": "",
          "meop_target": "",
          "meop_close_below": null,
          "relief": null,
          "relief_action": "open_valve",
          "relief_message": "",
          "relief_target": "",
          "relief_close_below": null,
          "soak_ms": 0
        }
      },
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
      "extras": {
        "thresholds": {
          "mawp": null,
          "mawp_action": "abort",
          "mawp_message": "",
          "mawp_target": "",
          "mawp_close_below": null,
          "meop": null,
          "meop_action": "open_valve",
          "meop_message": "",
          "meop_target": "",
          "meop_close_below": null,
          "relief": null,
          "relief_action": "open_valve",
          "relief_message": "",
          "relief_target": "",
          "relief_close_below": null,
          "soak_ms": 0
        }
      },
      "rotation": 0,
      "hide_lbl": false
    },
    {
      "id": "IGN_1",
      "type": "igniter",
      "label": "IGN_1",
      "hardware": {
        "relay": 48
      },
      "extras": {},
      "rotation": 0,
      "hide_lbl": false
    },
    {
      "id": "IGN_2",
      "type": "igniter",
      "label": "IGN_2",
      "hardware": {
        "relay": 49
      },
      "extras": {},
      "rotation": 0,
      "hide_lbl": false
    },
    {
      "id": "LAB_12",
      "type": "label",
      "label": "Fuel",
      "hardware": {},
      "extras": {},
      "rotation": 0,
      "hide_lbl": false
    },
    {
      "id": "LAB_13",
      "type": "label",
      "label": "     ----------------",
      "hardware": {},
      "extras": {},
      "rotation": 0,
      "hide_lbl": false
    },
    {
      "id": "LOA_4",
      "type": "load_cell",
      "label": "LC4",
      "hardware": {},
      "extras": {},
      "rotation": 0,
      "hide_lbl": false
    },
    {
      "id": "LOA_5",
      "type": "load_cell",
      "label": "LC5",
      "hardware": {},
      "extras": {},
      "rotation": 0,
      "hide_lbl": false
    },
    {
      "id": "LOA_6",
      "type": "load_cell",
      "label": "LC6",
      "hardware": {},
      "extras": {},
      "rotation": 0,
      "hide_lbl": false
    }
  ],
  "connections": [],
  "layout": {
    "TK_1": {
      "x": 640.0,
      "y": 190.0
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
      "x": 1000.0,
      "y": 440.0
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
      "y": -30.0
    },
    "LAB_4": {
      "x": 690.0,
      "y": -120.0
    },
    "VAL_4": {
      "x": 850.0,
      "y": 390.0
    },
    "VAL_5": {
      "x": 640.0,
      "y": 0.0
    },
    "VAL_6": {
      "x": 640.0,
      "y": -90.0
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
      "y": 170.0
    },
    "LAB_7": {
      "x": 760.0,
      "y": 150.0
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
      "x": 80.0,
      "y": 620.0
    },
    "LOA_2": {
      "x": 80.0,
      "y": 700.0
    },
    "LOA_3": {
      "x": 80.0,
      "y": 780.0
    },
    "TC_1": {
      "x": 220.0,
      "y": 620.0
    },
    "IGN_1": {
      "x": 220.0,
      "y": 700.0
    },
    "IGN_2": {
      "x": 220.0,
      "y": 780.0
    },
    "LAB_12": {
      "x": 640.0,
      "y": 100.0
    },
    "LAB_13": {
      "x": 640.0,
      "y": 120.0
    },
    "LOA_4": {
      "x": 150.0,
      "y": 620.0
    },
    "LOA_5": {
      "x": 150.0,
      "y": 700.0
    },
    "LOA_6": {
      "x": 150.0,
      "y": 780.0
    }
  },
  "lines": [
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
      "id": "line_0",
      "points": [
        {
          "x": 200.0,
          "y": 480.0
        },
        {
          "x": 200.0,
          "y": 360.0
        },
        {
          "x": 280.0,
          "y": 360.0
        },
        {
          "x": 280.0,
          "y": 480.0
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
      "fluid": "oxidizer",
      "connects": [],
      "dotted": false
    },
    {
      "id": "line_1",
      "points": [
        {
          "x": 570.0,
          "y": 650.0
        },
        {
          "x": 600.0,
          "y": 720.0
        },
        {
          "x": 680.0,
          "y": 720.0
        },
        {
          "x": 710.0,
          "y": 650.0
        },
        {
          "x": 570.0,
          "y": 650.0
        },
        {
          "x": 570.0,
          "y": 610.0
        },
        {
          "x": 710.0,
          "y": 610.0
        },
        {
          "x": 710.0,
          "y": 650.0
        }
      ],
      "fluid": "generic",
      "connects": [],
      "dotted": false
    },
    {
      "id": "line_2",
      "points": [
        {
          "x": 360.0,
          "y": 360.0
        },
        {
          "x": 540.0,
          "y": 360.0
        },
        {
          "x": 540.0,
          "y": 320.0
        },
        {
          "x": 540.0,
          "y": 360.0
        },
        {
          "x": 600.0,
          "y": 360.0
        },
        {
          "x": 640.0,
          "y": 360.0
        },
        {
          "x": 640.0,
          "y": 270.0
        },
        {
          "x": 640.0,
          "y": 410.0
        },
        {
          "x": 590.0,
          "y": 410.0
        },
        {
          "x": 640.0,
          "y": 410.0
        },
        {
          "x": 640.0,
          "y": 460.0
        }
      ],
      "fluid": "oxidizer",
      "connects": [],
      "dotted": false
    },
    {
      "id": "line_3",
      "points": [
        {
          "x": 640.0,
          "y": 460.0
        },
        {
          "x": 640.0,
          "y": 520.0
        },
        {
          "x": 590.0,
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
          "x": 640.0,
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
          "x": 670.0,
          "y": 580.0
        },
        {
          "x": 640.0,
          "y": 580.0
        }
      ],
      "fluid": "oxidizer",
      "connects": [],
      "dotted": false
    },
    {
      "id": "line_6",
      "points": [
        {
          "x": 480.0,
          "y": 230.0
        },
        {
          "x": 480.0,
          "y": 160.0
        },
        {
          "x": 480.0,
          "y": -50.0
        },
        {
          "x": 640.0,
          "y": -50.0
        },
        {
          "x": 640.0,
          "y": -90.0
        },
        {
          "x": 640.0,
          "y": 0.0
        }
      ],
      "fluid": "fuel",
      "connects": [],
      "dotted": false
    },
    {
      "id": "line_7",
      "points": [
        {
          "x": 640.0,
          "y": 0.0
        },
        {
          "x": 640.0,
          "y": 140.0
        }
      ],
      "fluid": "fuel",
      "connects": [],
      "dotted": false
    },
    {
      "id": "line_12",
      "points": [
        {
          "x": 640.0,
          "y": 60.0
        },
        {
          "x": 710.0,
          "y": 60.0
        },
        {
          "x": 710.0,
          "y": 170.0
        }
      ],
      "fluid": "fuel",
      "connects": [],
      "dotted": true
    },
    {
      "id": "line_13",
      "points": [
        {
          "x": 710.0,
          "y": 170.0
        },
        {
          "x": 710.0,
          "y": 410.0
        },
        {
          "x": 710.0,
          "y": 460.0
        }
      ],
      "fluid": "fuel",
      "connects": [],
      "dotted": true
    },
    {
      "id": "line_10",
      "points": [
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
          "y": 560.0
        },
        {
          "x": 640.0,
          "y": 610.0
        }
      ],
      "fluid": "fuel",
      "connects": [],
      "dotted": true
    },
    {
      "id": "line_14",
      "points": [
        {
          "x": 1000.0,
          "y": 660.0
        },
        {
          "x": 1000.0,
          "y": 590.0
        },
        {
          "x": 1000.0,
          "y": 490.0
        },
        {
          "x": 1050.0,
          "y": 490.0
        },
        {
          "x": 1000.0,
          "y": 490.0
        },
        {
          "x": 1000.0,
          "y": 440.0
        }
      ],
      "fluid": "pressurant",
      "connects": [],
      "dotted": false
    },
    {
      "id": "line_9",
      "points": [
        {
          "x": 1000.0,
          "y": 440.0
        },
        {
          "x": 1000.0,
          "y": 360.0
        },
        {
          "x": 960.0,
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
          "x": 650.0,
          "y": 360.0
        },
        {
          "x": 650.0,
          "y": 250.0
        }
      ],
      "fluid": "pressurant",
      "connects": [],
      "dotted": false
    }
  ],
  "parameters": {
    "tank_volume": 0.0,
    "notes": "",
    "system_mawp": 1600.0,
    "system_meop": 1300.0,
    "system_mawp_message": "",
    "system_meop_message": "",
    "terminal_count_s": 9.5
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
      "message_template": "P8 ({P8}) > 700",
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
      "message_template": "P8 ({P8}) > P7 ({P7})",
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
      "message_template": "P5 ({P5}) > P3 ({P3}) by 5 PSI for > {soak_ms}ms",
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
      "message_template": "P6 ({P6}) > P4 ({P4}) by 5 PSI for > {soak_ms}ms",
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
      "message_template": "",
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
      "message_template": "",
      "target_valve": "",
      "close_valve_below": null,
      "soak_ms": 0
    }
  ],
  "sequence": [],
  "sequences": [
    {
      "id": "seq_default",
      "name": "15 Second Fire",
      "steps": [
        {
          "name": "Terminal Count",
          "time_offset": 0.0,
          "open_valves": [],
          "is_terminal_count": true
        },
        {
          "name": "Ignition 1",
          "time_offset": 9.5,
          "open_valves": [
            "IGN_1",
            "GV_1"
          ],
          "is_terminal_count": false
        },
        {
          "name": "Main Valves",
          "time_offset": 10.0,
          "open_valves": [
            "BV_3",
            "GV_2",
            "GV_1",
            "IGN_1"
          ],
          "is_terminal_count": false
        },
        {
          "name": "Ignition 2",
          "time_offset": 10.4,
          "open_valves": [
            "IGN_2",
            "IGN_1",
            "GV_1",
            "GV_2",
            "BV_3"
          ],
          "is_terminal_count": false
        },
        {
          "name": "Shutdown",
          "time_offset": 15.0,
          "open_valves": [],
          "is_terminal_count": false
        }
      ]
    },
    {
      "id": "seq_d74eca00",
      "name": "5 Second Fire",
      "steps": [
        {
          "name": "Terminal Count",
          "time_offset": 0.0,
          "open_valves": [],
          "is_terminal_count": true
        },
        {
          "name": "Ignition 1",
          "time_offset": 9.5,
          "open_valves": [
            "IGN_1",
            "GV_1"
          ],
          "is_terminal_count": false
        },
        {
          "name": "Main Valves",
          "time_offset": 10.0,
          "open_valves": [
            "GV_1",
            "GV_2",
            "BV_3",
            "IGN_1"
          ],
          "is_terminal_count": false
        },
        {
          "name": "Ignition 2",
          "time_offset": 10.4,
          "open_valves": [
            "IGN_1",
            "IGN_2",
            "GV_1",
            "GV_2",
            "BV_3"
          ],
          "is_terminal_count": false
        },
        {
          "name": "Shutdown",
          "time_offset": 15.0,
          "open_valves": [],
          "is_terminal_count": false
        }
      ]
    }
  ],
  "active_sequence_id": "seq_default",
  "calc_channels": [
    {
      "id": "calc_57e94c77",
      "label": "Thrust",
      "role": "thrust",
      "unit": "lbf",
      "expression": "abs(LC1) + abs(LC2) + abs(LC3)",
      "constants": {},
      "enabled": true
    }
  ]
}