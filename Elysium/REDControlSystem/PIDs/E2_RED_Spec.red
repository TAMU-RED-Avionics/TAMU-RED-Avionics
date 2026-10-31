{
  "name": "Elysium 2 P&ID",
  "version": "2.0",
  "components": [
    {
      "id": "TK_1",
      "type": "tank",
      "label": "NT-1101",
      "hardware": {},
      "extras": {
        "notes": "Linde GN2 2200 K-bottle | GN2 | Vol: 1.54 CF MEOP: 2015 psig MAWP: 2015 psig",
        "link": "https://www.lindedirect.com/store/product-detail/nitrogen-(n2)-nitrogen-k/ni-k?srsltid=AU7gw4Wy8A9HvJT5sJ3vGlOW51eOfVhjuwy-960xYD_Pro0hbudjdc_R",
        "scale_x": 1.429,
        "scale_y": 1.6
      },
      "rotation": 0,
      "hide_lbl": false,
      "flip": false
    },
    {
      "id": "TK_2",
      "type": "tank",
      "label": "NT-1102",
      "hardware": {},
      "extras": {
        "notes": "Linde GN2 2200 K-bottle | GN2 | Vol: 1.54 CF MEOP: 2015 psig MAWP: 2015 psig",
        "link": "https://www.lindedirect.com/store/product-detail/nitrogen-(n2)-nitrogen-k/ni-k?srsltid=AU7gw4Wy8A9HvJT5sJ3vGlOW51eOfVhjuwy-960xYD_Pro0hbudjdc_R",
        "scale_x": 1.429,
        "scale_y": 1.6
      },
      "rotation": 0,
      "hide_lbl": false,
      "flip": false
    },
    {
      "id": "TK_3",
      "type": "tank",
      "label": "NT-1103",
      "hardware": {},
      "extras": {
        "notes": "Linde GN2 2200 K-bottle | GN2 | Vol: 1.54 CF MEOP: 2015 psig MAWP: 2015 psig",
        "link": "https://www.lindedirect.com/store/product-detail/nitrogen-(n2)-nitrogen-k/ni-k?srsltid=AU7gw4Wy8A9HvJT5sJ3vGlOW51eOfVhjuwy-960xYD_Pro0hbudjdc_R",
        "scale_x": 1.429,
        "scale_y": 1.6
      },
      "rotation": 0,
      "hide_lbl": false,
      "flip": false
    },
    {
      "id": "TK_4",
      "type": "tank",
      "label": "OT-1301",
      "hardware": {},
      "extras": {
        "notes": "Matheson Nippon 56lb Industrial Nitrous Oxide K-Bottle | N2O | Vol: 1.32 CF MEOP: 1050 psig MAWP: 2015 psig",
        "link": "https://us.nipponsanso.com/gases/nitrous-oxide-n2o/",
        "scale_x": 1.429,
        "scale_y": 1.6
      },
      "rotation": 0,
      "hide_lbl": false,
      "flip": false
    },
    {
      "id": "TK_5",
      "type": "tank",
      "label": "OT-1302",
      "hardware": {},
      "extras": {
        "notes": "Matheson Nippon 56lb Industrial Nitrous Oxide K-Bottle | N2O | Vol: 1.32 CF MEOP: 1050 psig MAWP: 2015 psig",
        "link": "https://us.nipponsanso.com/gases/nitrous-oxide-n2o/",
        "scale_x": 1.429,
        "scale_y": 1.6
      },
      "rotation": 0,
      "hide_lbl": false,
      "flip": false
    },
    {
      "id": "H_1",
      "type": "flex_hose",
      "label": "OH-1301",
      "hardware": {},
      "extras": {
        "notes": "6' Long 1/2\" JIC Hose",
        "link": "google.com/url?q=https://www.hydraulichoses.com/hoses/hydraulic-hose-assembly/1-2-hydraulic-hose-assembly/fa-ufw8-jic/fa-ufw8-jic-72&sa=D&source=editors&ust=1791777059518158&usg=AOvVaw0IlwoKNiNz2keo2lrpiCTY"
      },
      "rotation": 270,
      "hide_lbl": false,
      "flip": false
    },
    {
      "id": "PT_1",
      "type": "pressure",
      "label": "OPT-1301",
      "hardware": {
        "adc": 2
      },
      "extras": {
        "notes": "McMaster 1500 psi Pressure Transducer",
        "link": "https://www.mcmaster.com/6017N19/",
        "hw_id": "P2",
        "thresholds": {
          "mawp": null,
          "mawp_action": "abort",
          "mawp_message": "",
          "mawp_target": "",
          "mawp_close_below": null,
          "mawp_state": "",
          "meop": null,
          "meop_action": "open_valve",
          "meop_message": "",
          "meop_target": "",
          "meop_close_below": null,
          "meop_state": "",
          "relief": null,
          "relief_action": "open_valve",
          "relief_message": "",
          "relief_target": "",
          "relief_close_below": null,
          "relief_state": "",
          "soak_ms": 0
        }
      },
      "rotation": 0,
      "hide_lbl": false,
      "flip": false
    },
    {
      "id": "CV_1",
      "type": "check_valve",
      "label": "OC-1301",
      "hardware": {},
      "extras": {
        "notes": "McMaster 1/2\" MNPT High Flow Check Valve",
        "link": "https://www.mcmaster.com/1874N16/"
      },
      "rotation": 0,
      "hide_lbl": false,
      "flip": false
    },
    {
      "id": "H_2",
      "type": "flex_hose",
      "label": "NH-1102",
      "hardware": {},
      "extras": {
        "notes": "1' Long 1/4\" JIC Hose",
        "link": "https://www.hydraulichoses.com/hoses/hydraulic-hose-assembly/1-4-hydraulic-hose-assembly/fa-ufw4-jic/fa-ufw4-jic-12"
      },
      "rotation": 0,
      "hide_lbl": false,
      "flip": false
    },
    {
      "id": "PG_1",
      "type": "pressure_gauge",
      "label": "NPG-1101",
      "hardware": {},
      "extras": {
        "notes": "3000 psi 1/4\" MNPT Pressure Gauge",
        "link": "https://www.mcmaster.com/4089K61-4089K103/"
      },
      "rotation": 0,
      "hide_lbl": false,
      "flip": false
    },
    {
      "id": "PG_2",
      "type": "pressure_gauge",
      "label": "NPG-1102",
      "hardware": {},
      "extras": {},
      "rotation": 0,
      "hide_lbl": false,
      "flip": false
    },
    {
      "id": "PT_2",
      "type": "pressure",
      "label": "NPT-1101",
      "hardware": {
        "adc": 1
      },
      "extras": {
        "notes": "McMaster 1500 psi Pressure Transducer",
        "link": "https://www.mcmaster.com/6017N19/",
        "hw_id": "P1",
        "thresholds": {
          "mawp": null,
          "mawp_action": "abort",
          "mawp_message": "",
          "mawp_target": "",
          "mawp_close_below": null,
          "mawp_state": "",
          "meop": null,
          "meop_action": "open_valve",
          "meop_message": "",
          "meop_target": "",
          "meop_close_below": null,
          "meop_state": "",
          "relief": null,
          "relief_action": "open_valve",
          "relief_message": "",
          "relief_target": "",
          "relief_close_below": null,
          "relief_state": "",
          "soak_ms": 0
        }
      },
      "rotation": 0,
      "hide_lbl": false,
      "flip": false
    },
    {
      "id": "CV_2",
      "type": "check_valve",
      "label": "NC-1101",
      "hardware": {},
      "extras": {
        "notes": "McMaster 1/2\" MNPT High Flow Check Valve",
        "link": "https://www.mcmaster.com/1874N16/"
      },
      "rotation": 0,
      "hide_lbl": false,
      "flip": false
    },
    {
      "id": "H_3",
      "type": "flex_hose",
      "label": "NH-1103",
      "hardware": {},
      "extras": {
        "notes": "6' Long 1/2\" JIC Hose",
        "link": "google.com/url?q=https://www.hydraulichoses.com/hoses/hydraulic-hose-assembly/1-2-hydraulic-hose-assembly/fa-ufw8-jic/fa-ufw8-jic-72&sa=D&source=editors&ust=1791777059518158&usg=AOvVaw0IlwoKNiNz2keo2lrpiCTY"
      },
      "rotation": 180,
      "hide_lbl": false,
      "flip": false
    },
    {
      "id": "OR_1",
      "type": "orifice",
      "label": "NOR-1101",
      "hardware": {},
      "extras": {
        "notes": "McMaster Venting Orifice",
        "link": "https://www.mcmaster.com/2822T17-2822T255/",
        "label_offset": [
          50.4,
          -24.7
        ]
      },
      "rotation": 270,
      "hide_lbl": false,
      "flip": false
    },
    {
      "id": "PT_3",
      "type": "pressure",
      "label": "OPT-1502",
      "hardware": {
        "adc": 5
      },
      "extras": {
        "notes": "High Resolution 1500psi Pressure Transducer",
        "link": "https://www.mcmaster.com/3196K449/",
        "label_offset": [
          59.6,
          -28.2
        ],
        "hw_id": "P5",
        "thresholds": {
          "mawp": null,
          "mawp_action": "abort",
          "mawp_message": "",
          "mawp_target": "",
          "mawp_close_below": null,
          "mawp_state": "",
          "meop": null,
          "meop_action": "open_valve",
          "meop_message": "",
          "meop_target": "",
          "meop_close_below": null,
          "meop_state": "",
          "relief": null,
          "relief_action": "open_valve",
          "relief_message": "",
          "relief_target": "",
          "relief_close_below": null,
          "relief_state": "",
          "soak_ms": 0
        }
      },
      "rotation": 0,
      "hide_lbl": false,
      "flip": false
    },
    {
      "id": "H_4",
      "type": "flex_hose",
      "label": "FH-1401",
      "hardware": {},
      "extras": {
        "notes": "3' Long 1/2\" JIC Hose",
        "link": "google.com/url?q=https://www.hydraulichoses.com/hoses/hydraulic-hose-assembly/1-2-hydraulic-hose-assembly/fa-ufw8-jic/fa-ufw8-jic-36&sa=D&source=editors&ust=1791778467308429&usg=AOvVaw1yowrI1uk5XHaZwpmFE0jg",
        "label_offset": [
          104.6,
          -37.0
        ]
      },
      "rotation": 90,
      "hide_lbl": false,
      "flip": false
    },
    {
      "id": "PT_4",
      "type": "pressure",
      "label": "OPT-1501",
      "hardware": {
        "adc": 3
      },
      "extras": {
        "notes": "McMaster 1500 psi Pressure Transducer",
        "link": "google.com/url?q=https://www.mcmaster.com/6017n19/&sa=D&source=editors&ust=1791776789463683&usg=AOvVaw2m7GMnM4zjbmfVUhvYMv6a",
        "hw_id": "P3",
        "thresholds": {
          "mawp": null,
          "mawp_action": "abort",
          "mawp_message": "",
          "mawp_target": "",
          "mawp_close_below": null,
          "mawp_state": "",
          "meop": null,
          "meop_action": "open_valve",
          "meop_message": "",
          "meop_target": "",
          "meop_close_below": null,
          "meop_state": "",
          "relief": null,
          "relief_action": "open_valve",
          "relief_message": "",
          "relief_target": "",
          "relief_close_below": null,
          "relief_state": "",
          "soak_ms": 0
        }
      },
      "rotation": 0,
      "hide_lbl": false,
      "flip": false
    },
    {
      "id": "H_5",
      "type": "flex_hose",
      "label": "OH-1502",
      "hardware": {},
      "extras": {
        "notes": "3' Long 1/2\" JIC Hose",
        "link": "google.com/url?q=https://www.hydraulichoses.com/hoses/hydraulic-hose-assembly/1-2-hydraulic-hose-assembly/fa-ufw8-jic/fa-ufw8-jic-36&sa=D&source=editors&ust=1791778467308429&usg=AOvVaw1yowrI1uk5XHaZwpmFE0jg",
        "label_offset": [
          44.8,
          -15.8
        ]
      },
      "rotation": 90,
      "hide_lbl": false,
      "flip": false
    },
    {
      "id": "H_6",
      "type": "flex_hose",
      "label": "OH-1501",
      "hardware": {},
      "extras": {
        "notes": "3' Long 1/2\" JIC Hose",
        "link": "google.com/url?q=https://www.hydraulichoses.com/hoses/hydraulic-hose-assembly/1-2-hydraulic-hose-assembly/fa-ufw8-jic/fa-ufw8-jic-36&sa=D&source=editors&ust=1791778467308429&usg=AOvVaw1yowrI1uk5XHaZwpmFE0jg",
        "label_offset": [
          -42.3,
          -26.4
        ]
      },
      "rotation": 90,
      "hide_lbl": false,
      "flip": false
    },
    {
      "id": "PT_5",
      "type": "pressure",
      "label": "FPT-1401",
      "hardware": {
        "adc": 4
      },
      "extras": {
        "notes": "McMaster 1500 psi Pressure Transducer",
        "link": "google.com/url?q=https://www.mcmaster.com/6017n19/&sa=D&source=editors&ust=1791776789463683&usg=AOvVaw2m7GMnM4zjbmfVUhvYMv6a",
        "hw_id": "P4",
        "thresholds": {
          "mawp": null,
          "mawp_action": "abort",
          "mawp_message": "",
          "mawp_target": "",
          "mawp_close_below": null,
          "mawp_state": "",
          "meop": null,
          "meop_action": "open_valve",
          "meop_message": "",
          "meop_target": "",
          "meop_close_below": null,
          "meop_state": "",
          "relief": null,
          "relief_action": "open_valve",
          "relief_message": "",
          "relief_target": "",
          "relief_close_below": null,
          "relief_state": "",
          "soak_ms": 0
        }
      },
      "rotation": 0,
      "hide_lbl": false,
      "flip": false
    },
    {
      "id": "PT_6",
      "type": "pressure",
      "label": "FPT-1402",
      "hardware": {
        "adc": 6
      },
      "extras": {
        "notes": "High Resolution 1500psi Pressure Transducer",
        "link": "https://www.mcmaster.com/3196K449/",
        "hw_id": "P6",
        "thresholds": {
          "mawp": null,
          "mawp_action": "abort",
          "mawp_message": "",
          "mawp_target": "",
          "mawp_close_below": null,
          "mawp_state": "",
          "meop": null,
          "meop_action": "open_valve",
          "meop_message": "",
          "meop_target": "",
          "meop_close_below": null,
          "meop_state": "",
          "relief": null,
          "relief_action": "open_valve",
          "relief_message": "",
          "relief_target": "",
          "relief_close_below": null,
          "relief_state": "",
          "soak_ms": 0
        }
      },
      "rotation": 0,
      "hide_lbl": false,
      "flip": false
    },
    {
      "id": "ATM_1",
      "type": "to_atmosphere",
      "label": "ATM_1",
      "hardware": {},
      "extras": {},
      "rotation": 0,
      "hide_lbl": true,
      "flip": false
    },
    {
      "id": "ATM_2",
      "type": "to_atmosphere",
      "label": "ATM_2",
      "hardware": {},
      "extras": {},
      "rotation": 180,
      "hide_lbl": true,
      "flip": false
    },
    {
      "id": "ATM_3",
      "type": "to_atmosphere",
      "label": "ATM_3",
      "hardware": {},
      "extras": {},
      "rotation": 0,
      "hide_lbl": true,
      "flip": false
    },
    {
      "id": "TK_6",
      "type": "tank",
      "label": "FT-1201",
      "hardware": {},
      "extras": {
        "scale_x": 0.714,
        "scale_y": 0.8,
        "notes": "ETH | Vol: 1.54 CF MEOP: 100 psig MAWP: 100 psig",
        "label_offset": [
          -1.2,
          31.2
        ]
      },
      "rotation": 0,
      "hide_lbl": false,
      "flip": false
    },
    {
      "id": "P_1",
      "type": "pump",
      "label": "FP-1201",
      "hardware": {
        "relay": 18
      },
      "extras": {
        "notes": "Diesel Fuel Pump (fuel)",
        "link": "https://www.jegs.com/b/350-1794K?gad_source=1&gad_campaignid=17339122447&gbraid=0AAAAAD6OBRHWuweYpqMSE-KrT_G4e7_3d&gclid=CjwKCAjwirLWBhBBEiwAlItbEufFyX9gZJTB2p92PEkkeYrnvLmuoy08WCZPjPvK3XUgwlhSqQwvahoCBKkQAvD_BwE",
        "scale_x": 1.4,
        "scale_y": 1.0
      },
      "rotation": 270,
      "hide_lbl": false,
      "flip": false
    },
    {
      "id": "H_7",
      "type": "flex_hose",
      "label": "FH-1201",
      "hardware": {},
      "extras": {
        "notes": "50' Long 3/4\" Garden Hose",
        "link": "https://www.google.com/url?q=https://www.homedepot.com/p/Teknor-Apex-High-Performance-3-4-in-x-50-ft-Kink-Resistant-Durable-Contractor-Grade-Garden-Hose-9150-50/324672544%23overlay&sa=D&source=editors&ust=1791778937620042&usg=AOvVaw1b16jPFDCVbzJd47BzhPU4"
      },
      "rotation": 270,
      "hide_lbl": false,
      "flip": false
    },
    {
      "id": "CV_3",
      "type": "check_valve",
      "label": "FC-1401",
      "hardware": {},
      "extras": {
        "notes": "McMaster 1/2\" MNPT High Flow Check Valve",
        "link": "https://www.mcmaster.com/1874N16/"
      },
      "rotation": 90,
      "hide_lbl": false,
      "flip": false
    },
    {
      "id": "HEX_1",
      "type": "heat_exchanger",
      "label": "OHEX-1301",
      "hardware": {},
      "extras": {
        "notes": "20' Long 1/4\" Copper Coil",
        "link": "https://www.homedepot.com/pep/Everbilt-1-4-in-x-20-ft-Soft-Copper-Refrigeration-Coil-Tubing-D-04020PS/100343040?source=shoppingads&locale=en-US&fp=ggl&pla=&mtc=SHOPPING-BF-CDP-GGL-D26P-026_001_PIPE_FITTING-NA-NA-NA-PMAX-NA-NA-NA-NA-NBR-NA-NA-NEW-_PMAXTEST&cm_mmc=SHOPPING-BF-CDP-GGL-D26P-026_001_PIPE_FITTING-NA-NA-NA-PMAX-NA-NA-NA-NA-NBR-NA-NA-NEW-_PMAXTEST-17697557984--&gclsrc=aw.ds&gad_source=1&gad_campaignid=17687574624&gbraid=0AAAAADq61UdfOGtdWBgxVRxGl9b_f8vfw&gclid=CjwKCAjw56zWBhB0EiwAdPOQOQduy_WiL-omOvG1Kd2R9Glr8vE5InCBPBe7ZVdNCexZUIXIY6C02BoCiewQAvD_BwE"
      },
      "rotation": 270,
      "hide_lbl": false,
      "flip": false
    },
    {
      "id": "V_1",
      "type": "valve",
      "label": "OV-1302",
      "hardware": {},
      "extras": {
        "notes": "Part of the K-Bottle",
        "label_offset": [
          48.4,
          -26.9
        ]
      },
      "rotation": 270,
      "hide_lbl": false,
      "flip": false
    },
    {
      "id": "V_2",
      "type": "valve",
      "label": "OV-1301",
      "hardware": {},
      "extras": {
        "notes": "Part of the K-Bottle",
        "label_offset": [
          43.0,
          -26.9
        ]
      },
      "rotation": 270,
      "hide_lbl": false,
      "flip": false
    },
    {
      "id": "V_3",
      "type": "valve",
      "label": "NV-1103",
      "hardware": {},
      "extras": {
        "notes": "Part of the K-bottle",
        "label_offset": [
          37.7,
          -28.7
        ]
      },
      "rotation": 270,
      "hide_lbl": false,
      "flip": false
    },
    {
      "id": "V_4",
      "type": "valve",
      "label": "NV-1102",
      "hardware": {},
      "extras": {
        "notes": "Part of the K-bottle",
        "label_offset": [
          44.8,
          -28.7
        ]
      },
      "rotation": 270,
      "hide_lbl": false,
      "flip": false
    },
    {
      "id": "V_5",
      "type": "valve",
      "label": "NV-1101",
      "hardware": {},
      "extras": {
        "notes": "Part of the K-bottle",
        "label_offset": [
          39.5,
          -30.5
        ]
      },
      "rotation": 270,
      "hide_lbl": false,
      "flip": false
    },
    {
      "id": "P_2",
      "type": "pump",
      "label": "AP-1601",
      "hardware": {
        "relay": 19
      },
      "extras": {
        "notes": "20gal 200psi Air Compressor",
        "link": "google.com/url?q=https://www.homedepot.com/p/Husky-20-Gal-200-PSI-Oil-Free-Portable-Vertical-Electric-Air-Compressor-C202H/312074157&sa=D&source=editors&ust=1791779333527839&usg=AOvVaw1gg6S2SnOjUORsJM8K8kVh",
        "scale_x": 1.4,
        "scale_y": 1.4
      },
      "rotation": 0,
      "hide_lbl": false,
      "flip": true
    },
    {
      "id": "PT_7",
      "type": "pressure",
      "label": "MCC_P",
      "hardware": {
        "adc": 8
      },
      "extras": {
        "notes": "High Resolution 1000psi Pressure Transducer",
        "link": "https://www.mcmaster.com/3196K448/",
        "hw_id": "P8",
        "thresholds": {
          "mawp": null,
          "mawp_action": "abort",
          "mawp_message": "",
          "mawp_target": "",
          "mawp_close_below": null,
          "mawp_state": "",
          "meop": null,
          "meop_action": "open_valve",
          "meop_message": "",
          "meop_target": "",
          "meop_close_below": null,
          "meop_state": "",
          "relief": null,
          "relief_action": "open_valve",
          "relief_message": "",
          "relief_target": "",
          "relief_close_below": null,
          "relief_state": "",
          "soak_ms": 0
        }
      },
      "rotation": 0,
      "hide_lbl": false,
      "flip": false
    },
    {
      "id": "PT_8",
      "type": "pressure",
      "label": "OMI_P",
      "hardware": {
        "adc": 7
      },
      "extras": {
        "notes": "High Resolution 1000psi Pressure Transducer",
        "link": "https://www.mcmaster.com/3196K448/",
        "hw_id": "P7",
        "thresholds": {
          "mawp": null,
          "mawp_action": "abort",
          "mawp_message": "",
          "mawp_target": "",
          "mawp_close_below": null,
          "mawp_state": "",
          "meop": null,
          "meop_action": "open_valve",
          "meop_message": "",
          "meop_target": "",
          "meop_close_below": null,
          "meop_state": "",
          "relief": null,
          "relief_action": "open_valve",
          "relief_message": "",
          "relief_target": "",
          "relief_close_below": null,
          "relief_state": "",
          "soak_ms": 0
        }
      },
      "rotation": 0,
      "hide_lbl": false,
      "flip": false
    },
    {
      "id": "SV_1",
      "type": "solenoid",
      "label": "NV-1104",
      "hardware": {
        "relay": 10
      },
      "extras": {
        "notes": "160 Bar 12V NC US Solid Solenoid",
        "link": "https://ussolid.com/products/1-2-high-pressure-solenoid-valve-160-bar-stainless-steel-12v-dc-high-pressure-high-temperature-solenoid-valve-76-356-f-normally-closed?country=US&utm_source=google&utm_medium=cpc&utm_campaign=19623095036&utm_content=646389619121&utm_term=&gad_source=1&gad_campaignid=19623095036&gbraid=0AAAAAD2ek2oCpkMN_Nfsq45g84KDjY0gX&gclid=CjwKCAjw56zWBhB0EiwAdPOQOVCRzyvPDYvjj9GunTyr8Xk7oqfnClEGhzN5vIxk38DCra6UsYn33hoC96gQAvD_BwE",
        "hw_id": "NCS1"
      },
      "rotation": 270,
      "hide_lbl": false,
      "flip": false
    },
    {
      "id": "SV_2",
      "type": "solenoid",
      "label": "NV-1106",
      "hardware": {},
      "extras": {
        "notes": "160 Bar 12V NC US Solid Solenoid",
        "link": "https://ussolid.com/products/1-2-high-pressure-solenoid-valve-160-bar-stainless-steel-12v-dc-high-pressure-high-temperature-solenoid-valve-76-356-f-normally-closed?country=US&utm_source=google&utm_medium=cpc&utm_campaign=19623095036&utm_content=646389619121&utm_term=&gad_source=1&gad_campaignid=19623095036&gbraid=0AAAAAD2ek2oCpkMN_Nfsq45g84KDjY0gX&gclid=CjwKCAjw56zWBhB0EiwAdPOQOVCRzyvPDYvjj9GunTyr8Xk7oqfnClEGhzN5vIxk38DCra6UsYn33hoC96gQAvD_BwE",
        "label_offset": [
          0.0,
          26.4
        ]
      },
      "rotation": 270,
      "hide_lbl": false,
      "flip": false
    },
    {
      "id": "SV_3",
      "type": "solenoid",
      "label": "NV-1105",
      "hardware": {
        "relay": 12
      },
      "extras": {
        "notes": "160 Bar 12V NC US Solid Solenoid",
        "link": "https://ussolid.com/products/1-2-high-pressure-solenoid-valve-160-bar-stainless-steel-12v-dc-high-pressure-high-temperature-solenoid-valve-76-356-f-normally-closed?country=US&utm_source=google&utm_medium=cpc&utm_campaign=19623095036&utm_content=646389619121&utm_term=&gad_source=1&gad_campaignid=19623095036&gbraid=0AAAAAD2ek2oCpkMN_Nfsq45g84KDjY0gX&gclid=CjwKCAjw56zWBhB0EiwAdPOQOVCRzyvPDYvjj9GunTyr8Xk7oqfnClEGhzN5vIxk38DCra6UsYn33hoC96gQAvD_BwE",
        "label_offset": [
          47.5,
          -28.2
        ],
        "hw_id": "NCS3"
      },
      "rotation": 270,
      "hide_lbl": false,
      "flip": false
    },
    {
      "id": "RED_1",
      "type": "reducer",
      "label": "RED_1",
      "hardware": {},
      "extras": {},
      "rotation": 90,
      "hide_lbl": true,
      "flip": false
    },
    {
      "id": "RED_2",
      "type": "reducer",
      "label": "RED_2",
      "hardware": {},
      "extras": {},
      "rotation": 270,
      "hide_lbl": true,
      "flip": false
    },
    {
      "id": "SV_4",
      "type": "solenoid",
      "label": "FV-1201",
      "hardware": {
        "relay": 4
      },
      "extras": {
        "notes": "160 Bar 12V NC US Solid Solenoid",
        "link": "https://ussolid.com/products/1-2-high-pressure-solenoid-valve-160-bar-stainless-steel-12v-dc-high-pressure-high-temperature-solenoid-valve-76-356-f-normally-closed?country=US&utm_source=google&utm_medium=cpc&utm_campaign=19623095036&utm_content=646389619121&utm_term=&gad_source=1&gad_campaignid=19623095036&gbraid=0AAAAAD2ek2oCpkMN_Nfsq45g84KDjY0gX&gclid=CjwKCAjw56zWBhB0EiwAdPOQOVCRzyvPDYvjj9GunTyr8Xk7oqfnClEGhzN5vIxk38DCra6UsYn33hoC96gQAvD_BwE",
        "hw_id": "NCS5"
      },
      "rotation": 0,
      "hide_lbl": false,
      "flip": false
    },
    {
      "id": "SV_5",
      "type": "solenoid",
      "label": "OV-1303",
      "hardware": {
        "relay": 11
      },
      "extras": {
        "notes": "160 Bar 12V NC US Solid Solenoid",
        "link": "https://ussolid.com/products/1-2-high-pressure-solenoid-valve-160-bar-stainless-steel-12v-dc-high-pressure-high-temperature-solenoid-valve-76-356-f-normally-closed?country=US&utm_source=google&utm_medium=cpc&utm_campaign=19623095036&utm_content=646389619121&utm_term=&gad_source=1&gad_campaignid=19623095036&gbraid=0AAAAAD2ek2oCpkMN_Nfsq45g84KDjY0gX&gclid=CjwKCAjw56zWBhB0EiwAdPOQOVCRzyvPDYvjj9GunTyr8Xk7oqfnClEGhzN5vIxk38DCra6UsYn33hoC96gQAvD_BwE",
        "hw_id": "NCS2"
      },
      "rotation": 270,
      "hide_lbl": false,
      "flip": false
    },
    {
      "id": "H_8",
      "type": "flex_hose",
      "label": "NH-1101",
      "hardware": {},
      "extras": {
        "notes": "1' Long 1/4\" JIC Hose",
        "link": "https://www.hydraulichoses.com/hoses/hydraulic-hose-assembly/1-4-hydraulic-hose-assembly/fa-ufw4-jic/fa-ufw4-jic-12"
      },
      "rotation": 0,
      "hide_lbl": false,
      "flip": false
    },
    {
      "id": "TK_7",
      "type": "tank",
      "label": "FOT-1501",
      "hardware": {},
      "extras": {
        "scale_x": 1.429,
        "scale_y": 2.4,
        "notes": "N2O | Vol: 1.77 CF MEOP: 1250 psig MAWP: 1600 psig"
      },
      "rotation": 0,
      "hide_lbl": false,
      "flip": false
    },
    {
      "id": "TC_1",
      "type": "temperature",
      "label": "OTH-1501",
      "hardware": {
        "adc": 111
      },
      "extras": {
        "notes": "Dryer-Omega Ported Thermocouple ",
        "link": "https://www.dwyeromega.com/en-us/pipe-plug-thermocouple-probes-with-npt-fitting-and-lead-wire/TC-NPT/p/TC-K-NPT-U-72",
        "hw_id": "TC1",
        "thresholds": {
          "mawp": null,
          "mawp_action": "abort",
          "mawp_message": "",
          "mawp_target": "",
          "mawp_close_below": null,
          "mawp_state": "",
          "meop": null,
          "meop_action": "open_valve",
          "meop_message": "",
          "meop_target": "",
          "meop_close_below": null,
          "meop_state": "",
          "relief": null,
          "relief_action": "open_valve",
          "relief_message": "",
          "relief_target": "",
          "relief_close_below": null,
          "relief_state": "",
          "soak_ms": 0
        }
      },
      "rotation": 0,
      "hide_lbl": false,
      "flip": false
    },
    {
      "id": "CV_4",
      "type": "check_valve",
      "label": "FC-1201",
      "hardware": {},
      "extras": {
        "notes": "McMaster 1/2\" MNPT High Flow Check Valve",
        "link": "https://www.mcmaster.com/1874N16/"
      },
      "rotation": 0,
      "hide_lbl": false,
      "flip": false
    },
    {
      "id": "LBL_1",
      "type": "label",
      "label": "1250 psig",
      "hardware": {},
      "extras": {},
      "rotation": 0,
      "hide_lbl": false,
      "flip": false
    },
    {
      "id": "LBL_2",
      "type": "label",
      "label": "1500 psig",
      "hardware": {},
      "extras": {},
      "rotation": 0,
      "hide_lbl": false,
      "flip": false
    },
    {
      "id": "LBL_4",
      "type": "label",
      "label": "ETH",
      "hardware": {},
      "extras": {},
      "rotation": 0,
      "hide_lbl": false,
      "flip": false
    },
    {
      "id": "AV_1",
      "type": "actuated_valve",
      "label": "MOV",
      "hardware": {
        "relay": 17
      },
      "extras": {
        "label_offset": [
          29.9,
          -28.2
        ],
        "hw_id": "PA-BV2"
      },
      "rotation": 270,
      "hide_lbl": false,
      "flip": false
    },
    {
      "id": "AV_2",
      "type": "actuated_valve",
      "label": "FV-1202",
      "hardware": {
        "relay": 82
      },
      "extras": {
        "label_offset": [
          44.0,
          -28.2
        ],
        "actuator": {
          "min_pct": 0,
          "max_pct": 100,
          "safe_pct": 0,
          "open_pct": 100,
          "unit": "%",
          "presets": [
            0,
            25,
            50,
            75,
            100
          ],
          "step": 1
        }
      },
      "rotation": 270,
      "hide_lbl": false,
      "flip": false
    },
    {
      "id": "AV_3",
      "type": "actuated_valve",
      "label": "MFV",
      "hardware": {
        "relay": 83
      },
      "extras": {
        "label_offset": [
          33.5,
          -26.4
        ],
        "hw_id": "MFV",
        "actuator": {
          "min_pct": 0,
          "max_pct": 100,
          "safe_pct": 0,
          "open_pct": 100,
          "unit": "%",
          "presets": [
            0,
            25,
            50,
            75,
            100
          ],
          "step": 1
        }
      },
      "rotation": 270,
      "hide_lbl": false,
      "flip": false
    },
    {
      "id": "HREG_1",
      "type": "hand_regulator",
      "label": "NR-1101",
      "hardware": {},
      "extras": {
        "label_offset": [
          58.2,
          -16.1
        ]
      },
      "rotation": 270,
      "hide_lbl": false,
      "flip": false
    },
    {
      "id": "PRV_1",
      "type": "prv",
      "label": "NRV-1101",
      "hardware": {},
      "extras": {
        "label_offset": [
          60.5,
          -20.2
        ]
      },
      "rotation": 270,
      "hide_lbl": false,
      "flip": false
    },
    {
      "id": "LAB_11",
      "type": "label",
      "label": "N2O",
      "hardware": {},
      "extras": {},
      "rotation": 0,
      "hide_lbl": false,
      "flip": false
    },
    {
      "id": "LAB_12",
      "type": "label",
      "label": "N2O",
      "hardware": {},
      "extras": {},
      "rotation": 0,
      "hide_lbl": false,
      "flip": false
    },
    {
      "id": "LAB_13",
      "type": "label",
      "label": "N2O",
      "hardware": {},
      "extras": {},
      "rotation": 0,
      "hide_lbl": false,
      "flip": false
    },
    {
      "id": "LAB_14",
      "type": "label",
      "label": "GN2",
      "hardware": {},
      "extras": {},
      "rotation": 0,
      "hide_lbl": false,
      "flip": false
    },
    {
      "id": "LAB_15",
      "type": "label",
      "label": "GN2",
      "hardware": {},
      "extras": {},
      "rotation": 0,
      "hide_lbl": false,
      "flip": false
    },
    {
      "id": "LAB_16",
      "type": "label",
      "label": "GN2",
      "hardware": {},
      "extras": {},
      "rotation": 0,
      "hide_lbl": false,
      "flip": false
    },
    {
      "id": "LAB_17",
      "type": "label",
      "label": "ETH",
      "hardware": {},
      "extras": {},
      "rotation": 0,
      "hide_lbl": false,
      "flip": false
    },
    {
      "id": "PT_9",
      "type": "pressure",
      "label": "P9",
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
          "mawp_state": "",
          "meop": null,
          "meop_action": "open_valve",
          "meop_message": "",
          "meop_target": "",
          "meop_close_below": null,
          "meop_state": "",
          "relief": null,
          "relief_action": "open_valve",
          "relief_message": "",
          "relief_target": "",
          "relief_close_below": null,
          "relief_state": "",
          "soak_ms": 0
        }
      },
      "rotation": 0,
      "hide_lbl": false,
      "flip": false
    },
    {
      "id": "PT_10",
      "type": "pressure",
      "label": "P10",
      "hardware": {
        "adc": 10
      },
      "extras": {
        "thresholds": {
          "mawp": null,
          "mawp_action": "abort",
          "mawp_message": "",
          "mawp_target": "",
          "mawp_close_below": null,
          "mawp_state": "",
          "meop": null,
          "meop_action": "open_valve",
          "meop_message": "",
          "meop_target": "",
          "meop_close_below": null,
          "meop_state": "",
          "relief": null,
          "relief_action": "open_valve",
          "relief_message": "",
          "relief_target": "",
          "relief_close_below": null,
          "relief_state": "",
          "soak_ms": 0
        }
      },
      "rotation": 0,
      "hide_lbl": false,
      "flip": false
    },
    {
      "id": "PT_11",
      "type": "pressure",
      "label": "P11",
      "hardware": {
        "adc": 11
      },
      "extras": {
        "thresholds": {
          "mawp": null,
          "mawp_action": "abort",
          "mawp_message": "",
          "mawp_target": "",
          "mawp_close_below": null,
          "mawp_state": "",
          "meop": null,
          "meop_action": "open_valve",
          "meop_message": "",
          "meop_target": "",
          "meop_close_below": null,
          "meop_state": "",
          "relief": null,
          "relief_action": "open_valve",
          "relief_message": "",
          "relief_target": "",
          "relief_close_below": null,
          "relief_state": "",
          "soak_ms": 0
        }
      },
      "rotation": 0,
      "hide_lbl": false,
      "flip": false
    },
    {
      "id": "PT_12",
      "type": "pressure",
      "label": "P12",
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
          "mawp_state": "",
          "meop": null,
          "meop_action": "open_valve",
          "meop_message": "",
          "meop_target": "",
          "meop_close_below": null,
          "meop_state": "",
          "relief": null,
          "relief_action": "open_valve",
          "relief_message": "",
          "relief_target": "",
          "relief_close_below": null,
          "relief_state": "",
          "soak_ms": 0
        }
      },
      "rotation": 0,
      "hide_lbl": false,
      "flip": false
    },
    {
      "id": "LOA_1",
      "type": "load_cell",
      "label": "LC1",
      "hardware": {
        "adc": 25
      },
      "extras": {
        "thresholds": {
          "mawp": null,
          "mawp_action": "abort",
          "mawp_message": "",
          "mawp_target": "",
          "mawp_close_below": null,
          "mawp_state": "",
          "meop": null,
          "meop_action": "open_valve",
          "meop_message": "",
          "meop_target": "",
          "meop_close_below": null,
          "meop_state": "",
          "relief": null,
          "relief_action": "open_valve",
          "relief_message": "",
          "relief_target": "",
          "relief_close_below": null,
          "relief_state": "",
          "soak_ms": 0
        }
      },
      "rotation": 0,
      "hide_lbl": false,
      "flip": false
    },
    {
      "id": "LOA_2",
      "type": "load_cell",
      "label": "LC2",
      "hardware": {
        "adc": 26
      },
      "extras": {
        "thresholds": {
          "mawp": null,
          "mawp_action": "abort",
          "mawp_message": "",
          "mawp_target": "",
          "mawp_close_below": null,
          "mawp_state": "",
          "meop": null,
          "meop_action": "open_valve",
          "meop_message": "",
          "meop_target": "",
          "meop_close_below": null,
          "meop_state": "",
          "relief": null,
          "relief_action": "open_valve",
          "relief_message": "",
          "relief_target": "",
          "relief_close_below": null,
          "relief_state": "",
          "soak_ms": 0
        }
      },
      "rotation": 0,
      "hide_lbl": false,
      "flip": false
    },
    {
      "id": "LOA_3",
      "type": "load_cell",
      "label": "LC3",
      "hardware": {
        "adc": 27
      },
      "extras": {
        "thresholds": {
          "mawp": null,
          "mawp_action": "abort",
          "mawp_message": "",
          "mawp_target": "",
          "mawp_close_below": null,
          "mawp_state": "",
          "meop": null,
          "meop_action": "open_valve",
          "meop_message": "",
          "meop_target": "",
          "meop_close_below": null,
          "meop_state": "",
          "relief": null,
          "relief_action": "open_valve",
          "relief_message": "",
          "relief_target": "",
          "relief_close_below": null,
          "relief_state": "",
          "soak_ms": 0
        }
      },
      "rotation": 0,
      "hide_lbl": false,
      "flip": false
    },
    {
      "id": "LOA_4",
      "type": "load_cell",
      "label": "LC4",
      "hardware": {
        "adc": 28
      },
      "extras": {
        "thresholds": {
          "mawp": null,
          "mawp_action": "abort",
          "mawp_message": "",
          "mawp_target": "",
          "mawp_close_below": null,
          "mawp_state": "",
          "meop": null,
          "meop_action": "open_valve",
          "meop_message": "",
          "meop_target": "",
          "meop_close_below": null,
          "meop_state": "",
          "relief": null,
          "relief_action": "open_valve",
          "relief_message": "",
          "relief_target": "",
          "relief_close_below": null,
          "relief_state": "",
          "soak_ms": 0
        }
      },
      "rotation": 0,
      "hide_lbl": false,
      "flip": false
    },
    {
      "id": "LOA_5",
      "type": "load_cell",
      "label": "LC5",
      "hardware": {
        "adc": 29
      },
      "extras": {
        "thresholds": {
          "mawp": null,
          "mawp_action": "abort",
          "mawp_message": "",
          "mawp_target": "",
          "mawp_close_below": null,
          "mawp_state": "",
          "meop": null,
          "meop_action": "open_valve",
          "meop_message": "",
          "meop_target": "",
          "meop_close_below": null,
          "meop_state": "",
          "relief": null,
          "relief_action": "open_valve",
          "relief_message": "",
          "relief_target": "",
          "relief_close_below": null,
          "relief_state": "",
          "soak_ms": 0
        }
      },
      "rotation": 0,
      "hide_lbl": false,
      "flip": false
    },
    {
      "id": "LOA_6",
      "type": "load_cell",
      "label": "LC6",
      "hardware": {
        "adc": 30
      },
      "extras": {
        "thresholds": {
          "mawp": null,
          "mawp_action": "abort",
          "mawp_message": "",
          "mawp_target": "",
          "mawp_close_below": null,
          "mawp_state": "",
          "meop": null,
          "meop_action": "open_valve",
          "meop_message": "",
          "meop_target": "",
          "meop_close_below": null,
          "meop_state": "",
          "relief": null,
          "relief_action": "open_valve",
          "relief_message": "",
          "relief_target": "",
          "relief_close_below": null,
          "relief_state": "",
          "soak_ms": 0
        }
      },
      "rotation": 0,
      "hide_lbl": false,
      "flip": false
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
      "hide_lbl": false,
      "flip": false
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
      "hide_lbl": false,
      "flip": false
    },
    {
      "id": "BRAYPWR_1",
      "type": "solenoid",
      "label": "BRAY-PWR",
      "hardware": {
        "relay": 9
      },
      "extras": {
        "notes": "Relay 9 -> external 12 V relay that powers the Bray positioner card (AD5420, daughtercard J9). The firmware commands the Bray to 0% (4 mA) before dropping this relay on every abort; open it before commanding MFV."
      },
      "rotation": 270,
      "hide_lbl": false,
      "flip": false
    }
  ],
  "connections": [],
  "layout": {
    "TK_1": {
      "x": 330.0,
      "y": 1120.0
    },
    "TK_2": {
      "x": 480.0,
      "y": 1120.0
    },
    "TK_3": {
      "x": 630.0,
      "y": 1120.0
    },
    "TK_4": {
      "x": 870.0,
      "y": 1120.0
    },
    "TK_5": {
      "x": 1020.0,
      "y": 1120.0
    },
    "H_1": {
      "x": 940.0,
      "y": 690.0
    },
    "PT_1": {
      "x": 1080.0,
      "y": 680.0
    },
    "CV_1": {
      "x": 1170.0,
      "y": 630.0
    },
    "H_2": {
      "x": 570.0,
      "y": 930.0
    },
    "PG_1": {
      "x": 420.0,
      "y": 870.0
    },
    "PG_2": {
      "x": 440.0,
      "y": 720.0
    },
    "PT_2": {
      "x": 520.0,
      "y": 720.0
    },
    "CV_2": {
      "x": 540.0,
      "y": 570.0
    },
    "H_3": {
      "x": 750.0,
      "y": 570.0
    },
    "OR_1": {
      "x": 840.0,
      "y": 430.0
    },
    "PT_3": {
      "x": 1300.0,
      "y": 750.0
    },
    "H_4": {
      "x": 1260.0,
      "y": 870.0
    },
    "PT_4": {
      "x": 1300.0,
      "y": 630.0
    },
    "H_5": {
      "x": 1320.0,
      "y": 870.0
    },
    "H_6": {
      "x": 1200.0,
      "y": 870.0
    },
    "PT_5": {
      "x": 1540.0,
      "y": 570.0
    },
    "PT_6": {
      "x": 1540.0,
      "y": 690.0
    },
    "ATM_1": {
      "x": 840.0,
      "y": 410.0
    },
    "ATM_2": {
      "x": 840.0,
      "y": 670.0
    },
    "ATM_3": {
      "x": 630.0,
      "y": 470.0
    },
    "TK_6": {
      "x": 120.0,
      "y": 1180.0
    },
    "P_1": {
      "x": 90.0,
      "y": 1070.0
    },
    "H_7": {
      "x": 90.0,
      "y": 930.0
    },
    "CV_3": {
      "x": 1500.0,
      "y": 750.0
    },
    "HEX_1": {
      "x": 940.0,
      "y": 870.0
    },
    "V_1": {
      "x": 1020.0,
      "y": 1010.0
    },
    "V_2": {
      "x": 870.0,
      "y": 1010.0
    },
    "V_3": {
      "x": 630.0,
      "y": 1010.0
    },
    "V_4": {
      "x": 480.0,
      "y": 1010.0
    },
    "V_5": {
      "x": 330.0,
      "y": 1010.0
    },
    "P_2": {
      "x": 1550.0,
      "y": 1140.0
    },
    "PT_7": {
      "x": 1140.0,
      "y": 990.0
    },
    "PT_8": {
      "x": 1140.0,
      "y": 920.0
    },
    "SV_1": {
      "x": 480.0,
      "y": 660.0
    },
    "SV_2": {
      "x": 840.0,
      "y": 650.0
    },
    "SV_3": {
      "x": 840.0,
      "y": 490.0
    },
    "RED_1": {
      "x": 510.0,
      "y": 930.0
    },
    "RED_2": {
      "x": 450.0,
      "y": 930.0
    },
    "SV_4": {
      "x": 1110.0,
      "y": 150.0
    },
    "SV_5": {
      "x": 940.0,
      "y": 780.0
    },
    "H_8": {
      "x": 390.0,
      "y": 930.0
    },
    "TK_7": {
      "x": 1260.0,
      "y": 310.0
    },
    "TC_1": {
      "x": 1300.0,
      "y": 530.0
    },
    "CV_4": {
      "x": 1200.0,
      "y": 150.0
    },
    "LBL_1": {
      "x": 540.0,
      "y": 770.0
    },
    "LBL_2": {
      "x": 690.0,
      "y": 450.0
    },
    "LBL_4": {
      "x": 1260.0,
      "y": 210.0
    },
    "AV_1": {
      "x": 1260.0,
      "y": 700.0
    },
    "AV_2": {
      "x": 1260.0,
      "y": 100.0
    },
    "AV_3": {
      "x": 1500.0,
      "y": 640.0
    },
    "HREG_1": {
      "x": 480.0,
      "y": 810.0
    },
    "PRV_1": {
      "x": 630.0,
      "y": 490.0
    },
    "LAB_11": {
      "x": 1260.0,
      "y": 280.0
    },
    "LAB_12": {
      "x": 870.0,
      "y": 1090.0
    },
    "LAB_13": {
      "x": 1020.0,
      "y": 1090.0
    },
    "LAB_14": {
      "x": 330.0,
      "y": 1090.0
    },
    "LAB_15": {
      "x": 480.0,
      "y": 1090.0
    },
    "LAB_16": {
      "x": 630.0,
      "y": 1090.0
    },
    "LAB_17": {
      "x": 120.0,
      "y": 1150.0
    },
    "PT_9": {
      "x": 330.0,
      "y": 1260.0
    },
    "PT_10": {
      "x": 430.0,
      "y": 1260.0
    },
    "PT_11": {
      "x": 530.0,
      "y": 1260.0
    },
    "PT_12": {
      "x": 630.0,
      "y": 1260.0
    },
    "LOA_1": {
      "x": -260.0,
      "y": 620.0
    },
    "LOA_2": {
      "x": -140.0,
      "y": 620.0
    },
    "LOA_3": {
      "x": -260.0,
      "y": 750.0
    },
    "LOA_4": {
      "x": -140.0,
      "y": 750.0
    },
    "LOA_5": {
      "x": -260.0,
      "y": 880.0
    },
    "LOA_6": {
      "x": -140.0,
      "y": 880.0
    },
    "IGN_1": {
      "x": -260.0,
      "y": 1000.0
    },
    "IGN_2": {
      "x": -140.0,
      "y": 1000.0
    },
    "BRAYPWR_1": {
      "x": 1620.0,
      "y": 640.0
    }
  },
  "lines": [
    {
      "id": "line_0",
      "points": [
        {
          "x": 540.0,
          "y": 570.0
        },
        {
          "x": 750.0,
          "y": 570.0
        }
      ],
      "fluid": "purge",
      "connects": [
        "CV_2",
        "H_3"
      ],
      "dotted": false
    },
    {
      "id": "line_1",
      "points": [
        {
          "x": 440.0,
          "y": 720.0
        },
        {
          "x": 520.0,
          "y": 720.0
        }
      ],
      "fluid": "purge",
      "connects": [
        "PG_2",
        "PT_2"
      ],
      "dotted": false
    },
    {
      "id": "line_3",
      "points": [
        {
          "x": 1300.0,
          "y": 630.0
        },
        {
          "x": 1170.0,
          "y": 630.0
        }
      ],
      "fluid": "oxidizer",
      "connects": [
        "PT_4",
        "CV_1"
      ],
      "dotted": false
    },
    {
      "id": "line_7",
      "points": [
        {
          "x": 840.0,
          "y": 470.0
        },
        {
          "x": 840.0,
          "y": 450.0
        }
      ],
      "fluid": "purge",
      "connects": [
        "SV_3",
        "OR_1"
      ],
      "dotted": false
    },
    {
      "id": "line_8",
      "points": [
        {
          "x": 870.0,
          "y": 990.0
        },
        {
          "x": 870.0,
          "y": 930.0
        },
        {
          "x": 1020.0,
          "y": 930.0
        },
        {
          "x": 1020.0,
          "y": 990.0
        }
      ],
      "fluid": "oxidizer",
      "connects": [
        "V_2",
        "V_1"
      ],
      "dotted": false
    },
    {
      "id": "line_9",
      "points": [
        {
          "x": 940.0,
          "y": 930.0
        },
        {
          "x": 940.0,
          "y": 870.0
        }
      ],
      "fluid": "oxidizer",
      "connects": [],
      "dotted": false
    },
    {
      "id": "line_10",
      "points": [
        {
          "x": 940.0,
          "y": 870.0
        },
        {
          "x": 940.0,
          "y": 780.0
        }
      ],
      "fluid": "oxidizer",
      "connects": [
        "HEX_1",
        "SV_5"
      ],
      "dotted": false
    },
    {
      "id": "line_11",
      "points": [
        {
          "x": 940.0,
          "y": 780.0
        },
        {
          "x": 940.0,
          "y": 690.0
        }
      ],
      "fluid": "oxidizer",
      "connects": [
        "SV_5",
        "H_1"
      ],
      "dotted": false
    },
    {
      "id": "line_12",
      "points": [
        {
          "x": 1170.0,
          "y": 630.0
        },
        {
          "x": 940.0,
          "y": 630.0
        },
        {
          "x": 940.0,
          "y": 690.0
        }
      ],
      "fluid": "oxidizer",
      "connects": [
        "CV_1",
        "H_1"
      ],
      "dotted": false
    },
    {
      "id": "line_13",
      "points": [
        {
          "x": 1080.0,
          "y": 630.0
        },
        {
          "x": 1080.0,
          "y": 680.0
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
          "x": 330.0,
          "y": 990.0
        },
        {
          "x": 330.0,
          "y": 930.0
        },
        {
          "x": 390.0,
          "y": 930.0
        }
      ],
      "fluid": "purge",
      "connects": [
        "V_5",
        "H_8"
      ],
      "dotted": false
    },
    {
      "id": "line_15",
      "points": [
        {
          "x": 630.0,
          "y": 990.0
        },
        {
          "x": 630.0,
          "y": 930.0
        },
        {
          "x": 570.0,
          "y": 930.0
        }
      ],
      "fluid": "purge",
      "connects": [
        "V_3",
        "H_2"
      ],
      "dotted": false
    },
    {
      "id": "line_17",
      "points": [
        {
          "x": 540.0,
          "y": 570.0
        },
        {
          "x": 480.0,
          "y": 570.0
        },
        {
          "x": 480.0,
          "y": 640.0
        }
      ],
      "fluid": "purge",
      "connects": [
        "CV_2",
        "SV_1"
      ],
      "dotted": false
    },
    {
      "id": "line_18",
      "points": [
        {
          "x": 630.0,
          "y": 510.0
        },
        {
          "x": 630.0,
          "y": 570.0
        }
      ],
      "fluid": "purge",
      "connects": [],
      "dotted": false
    },
    {
      "id": "line_19",
      "points": [
        {
          "x": 1200.0,
          "y": 150.0
        },
        {
          "x": 1110.0,
          "y": 150.0
        }
      ],
      "fluid": "fuel",
      "connects": [
        "CV_4",
        "SV_4"
      ],
      "dotted": false
    },
    {
      "id": "line_21",
      "points": [
        {
          "x": 1310.0,
          "y": 750.0
        },
        {
          "x": 1260.0,
          "y": 750.0
        }
      ],
      "fluid": "generic",
      "connects": [],
      "dotted": false
    },
    {
      "id": "line_22",
      "points": [
        {
          "x": 1260.0,
          "y": 930.0
        },
        {
          "x": 1260.0,
          "y": 870.0
        }
      ],
      "fluid": "fuel",
      "connects": [],
      "dotted": false
    },
    {
      "id": "line_23",
      "points": [
        {
          "x": 1320.0,
          "y": 930.0
        },
        {
          "x": 1320.0,
          "y": 870.0
        }
      ],
      "fluid": "oxidizer",
      "connects": [],
      "dotted": false
    },
    {
      "id": "line_24",
      "points": [
        {
          "x": 1200.0,
          "y": 930.0
        },
        {
          "x": 1200.0,
          "y": 870.0
        }
      ],
      "fluid": "oxidizer",
      "connects": [],
      "dotted": false
    },
    {
      "id": "line_25",
      "points": [
        {
          "x": 1500.0,
          "y": 570.0
        },
        {
          "x": 1540.0,
          "y": 570.0
        }
      ],
      "fluid": "generic",
      "connects": [],
      "dotted": false
    },
    {
      "id": "line_26",
      "points": [
        {
          "x": 1500.0,
          "y": 690.0
        },
        {
          "x": 1540.0,
          "y": 690.0
        }
      ],
      "fluid": "generic",
      "connects": [],
      "dotted": false
    },
    {
      "id": "line_27",
      "points": [
        {
          "x": 1200.0,
          "y": 870.0
        },
        {
          "x": 1200.0,
          "y": 780.0
        },
        {
          "x": 1260.0,
          "y": 780.0
        }
      ],
      "fluid": "oxidizer",
      "connects": [],
      "dotted": false
    },
    {
      "id": "line_28",
      "points": [
        {
          "x": 840.0,
          "y": 630.0
        },
        {
          "x": 840.0,
          "y": 510.0
        }
      ],
      "fluid": "purge",
      "connects": [
        "SV_2",
        "SV_3"
      ],
      "dotted": false
    },
    {
      "id": "line_29",
      "points": [
        {
          "x": 120.0,
          "y": 1130.0
        },
        {
          "x": 120.0,
          "y": 1070.0
        }
      ],
      "fluid": "fuel",
      "connects": [
        "TK_6",
        "P_1"
      ],
      "dotted": false
    },
    {
      "id": "line_30",
      "points": [
        {
          "x": 90.0,
          "y": 1040.0
        },
        {
          "x": 90.0,
          "y": 930.0
        }
      ],
      "fluid": "fuel",
      "connects": [
        "P_1",
        "H_7"
      ],
      "dotted": false
    },
    {
      "id": "line_31",
      "points": [
        {
          "x": 90.0,
          "y": 930.0
        },
        {
          "x": 90.0,
          "y": 150.0
        },
        {
          "x": 1110.0,
          "y": 150.0
        }
      ],
      "fluid": "fuel",
      "connects": [
        "H_7",
        "SV_4"
      ],
      "dotted": false
    },
    {
      "id": "line_32",
      "points": [
        {
          "x": 1260.0,
          "y": 870.0
        },
        {
          "x": 1260.0,
          "y": 810.0
        },
        {
          "x": 1500.0,
          "y": 810.0
        },
        {
          "x": 1500.0,
          "y": 750.0
        }
      ],
      "fluid": "fuel",
      "connects": [
        "H_4",
        "CV_3"
      ],
      "dotted": false
    },
    {
      "id": "line_33",
      "points": [
        {
          "x": 1180.0,
          "y": 960.0
        },
        {
          "x": 1180.0,
          "y": 1080.0
        },
        {
          "x": 1240.0,
          "y": 1140.0
        },
        {
          "x": 1180.0,
          "y": 1260.0
        },
        {
          "x": 1170.0,
          "y": 1260.0
        },
        {
          "x": 1230.0,
          "y": 1140.0
        },
        {
          "x": 1170.0,
          "y": 1080.0
        },
        {
          "x": 1170.0,
          "y": 960.0
        },
        {
          "x": 1350.0,
          "y": 960.0
        },
        {
          "x": 1350.0,
          "y": 1080.0
        },
        {
          "x": 1290.0,
          "y": 1140.0
        },
        {
          "x": 1350.0,
          "y": 1260.0
        },
        {
          "x": 1340.0,
          "y": 1260.0
        },
        {
          "x": 1280.0,
          "y": 1140.0
        },
        {
          "x": 1340.0,
          "y": 1080.0
        },
        {
          "x": 1340.0,
          "y": 960.0
        }
      ],
      "fluid": "generic",
      "connects": [],
      "dotted": false
    },
    {
      "id": "line_34",
      "points": [
        {
          "x": 1170.0,
          "y": 990.0
        },
        {
          "x": 1170.0,
          "y": 930.0
        },
        {
          "x": 1350.0,
          "y": 930.0
        },
        {
          "x": 1350.0,
          "y": 960.0
        }
      ],
      "fluid": "generic",
      "connects": [],
      "dotted": false
    },
    {
      "id": "line_36",
      "points": [
        {
          "x": 1410.0,
          "y": 800.0
        },
        {
          "x": 1230.0,
          "y": 800.0
        },
        {
          "x": 1230.0,
          "y": 700.0
        }
      ],
      "fluid": "generic",
      "connects": [],
      "dotted": false
    },
    {
      "id": "line_37",
      "points": [
        {
          "x": 1180.0,
          "y": 930.0
        },
        {
          "x": 1180.0,
          "y": 920.0
        },
        {
          "x": 1140.0,
          "y": 920.0
        }
      ],
      "fluid": "generic",
      "connects": [],
      "dotted": false
    },
    {
      "id": "line_38",
      "points": [
        {
          "x": 510.0,
          "y": 930.0
        },
        {
          "x": 570.0,
          "y": 930.0
        }
      ],
      "fluid": "purge",
      "connects": [
        "RED_1",
        "H_2"
      ],
      "dotted": false
    },
    {
      "id": "line_39",
      "points": [
        {
          "x": 450.0,
          "y": 930.0
        },
        {
          "x": 510.0,
          "y": 930.0
        }
      ],
      "fluid": "purge",
      "connects": [
        "RED_2",
        "RED_1"
      ],
      "dotted": false
    },
    {
      "id": "line_40",
      "points": [
        {
          "x": 390.0,
          "y": 930.0
        },
        {
          "x": 450.0,
          "y": 930.0
        }
      ],
      "fluid": "purge",
      "connects": [
        "H_8",
        "RED_2"
      ],
      "dotted": false
    },
    {
      "id": "line_41",
      "points": [
        {
          "x": 1300.0,
          "y": 520.0
        },
        {
          "x": 1300.0,
          "y": 400.0
        }
      ],
      "fluid": "generic",
      "connects": [
        "TC_1",
        "TK_7"
      ],
      "dotted": false
    },
    {
      "id": "line_43",
      "points": [
        {
          "x": 750.0,
          "y": 570.0
        },
        {
          "x": 1230.0,
          "y": 570.0
        },
        {
          "x": 1230.0,
          "y": 390.0
        }
      ],
      "fluid": "purge",
      "connects": [
        "H_3",
        "TK_7"
      ],
      "dotted": false
    },
    {
      "id": "line_4",
      "points": [
        {
          "x": 1320.0,
          "y": 850.0
        },
        {
          "x": 1320.0,
          "y": 780.0
        },
        {
          "x": 1260.0,
          "y": 780.0
        },
        {
          "x": 1260.0,
          "y": 720.0
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
          "x": 1260.0,
          "y": 680.0
        },
        {
          "x": 1260.0,
          "y": 630.0
        }
      ],
      "fluid": "oxidizer",
      "connects": [],
      "dotted": false
    },
    {
      "id": "line_5",
      "points": [
        {
          "x": 1500.0,
          "y": 730.0
        },
        {
          "x": 1500.0,
          "y": 660.0
        }
      ],
      "fluid": "fuel",
      "connects": [],
      "dotted": false
    },
    {
      "id": "line_20",
      "points": [
        {
          "x": 1500.0,
          "y": 620.0
        },
        {
          "x": 1500.0,
          "y": 150.0
        },
        {
          "x": 1220.0,
          "y": 150.0
        }
      ],
      "fluid": "fuel",
      "connects": [],
      "dotted": false
    },
    {
      "id": "line_42",
      "points": [
        {
          "x": 1260.0,
          "y": 120.0
        },
        {
          "x": 1260.0,
          "y": 170.0
        }
      ],
      "fluid": "fuel",
      "connects": [],
      "dotted": false
    },
    {
      "id": "line_35",
      "points": [
        {
          "x": 1520.0,
          "y": 1140.0
        },
        {
          "x": 1410.0,
          "y": 1140.0
        },
        {
          "x": 1410.0,
          "y": 700.0
        },
        {
          "x": 1470.0,
          "y": 700.0
        },
        {
          "x": 1470.0,
          "y": 640.0
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
          "x": 480.0,
          "y": 930.0
        },
        {
          "x": 480.0,
          "y": 830.0
        }
      ],
      "fluid": "purge",
      "connects": [],
      "dotted": false
    },
    {
      "id": "line_16",
      "points": [
        {
          "x": 480.0,
          "y": 790.0
        },
        {
          "x": 480.0,
          "y": 680.0
        }
      ],
      "fluid": "purge",
      "connects": [],
      "dotted": false
    },
    {
      "id": "line_44",
      "points": [
        {
          "x": 430.0,
          "y": 870.0
        },
        {
          "x": 480.0,
          "y": 870.0
        }
      ],
      "fluid": "purge",
      "connects": [],
      "dotted": false
    },
    {
      "id": "line_45",
      "points": [
        {
          "x": 1260.0,
          "y": 630.0
        },
        {
          "x": 1260.0,
          "y": 390.0
        }
      ],
      "fluid": "oxidizer",
      "connects": [],
      "dotted": false
    },
    {
      "id": "line_46",
      "points": [
        {
          "x": 480.0,
          "y": 930.0
        },
        {
          "x": 480.0,
          "y": 1010.0
        }
      ],
      "fluid": "purge",
      "connects": [],
      "dotted": false
    }
  ],
  "parameters": {
    "tank_volume": 0.0,
    "notes": "",
    "system_mawp": null,
    "system_meop": null,
    "system_mawp_message": "",
    "system_meop_message": "",
    "system_mawp_state": "",
    "system_prewarn_pct": 90.0,
    "terminal_count_s": 10.0
  },
  "rules": [
    {
      "id": "logic_rule_1",
      "abort_state": "",
      "condition_type": "expression",
      "action": "abort",
      "enabled": false,
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
      "abort_state": "",
      "condition_type": "expression",
      "action": "abort",
      "enabled": false,
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
      "abort_state": "",
      "condition_type": "expression",
      "action": "abort",
      "enabled": false,
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
      "abort_state": "",
      "condition_type": "expression",
      "action": "abort",
      "enabled": false,
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
      "abort_state": "",
      "condition_type": "expression",
      "action": "open_valve",
      "enabled": false,
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
      "abort_state": "",
      "condition_type": "expression",
      "action": "warn",
      "enabled": false,
      "sensor_id": "",
      "expression": "P2 > 1375",
      "description": "Warning: P2 > 1375. Opening NCS3...",
      "message_template": "",
      "target_valve": "",
      "close_valve_below": null,
      "soak_ms": 0
    }
  ],
  "abort_states": [
    {
      "id": "default",
      "name": "Default Abort",
      "valves": {
        "SV_1": false,
        "SV_5": false,
        "SV_3": false,
        "SV_2": false,
        "SV_4": false,
        "AV_1": false,
        "AV_2": false,
        "AV_3": false,
        "SV_6": false,
        "P_1": false,
        "P_2": false,
        "BRAYPWR_1": false
      },
      "confirmed": true
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
            "BRAYPWR_1"
          ],
          "is_terminal_count": false
        },
        {
          "name": "Main Valves",
          "time_offset": 10.0,
          "open_valves": [
            "AV_3",
            "IGN_1",
            "BRAYPWR_1"
          ],
          "is_terminal_count": false
        },
        {
          "name": "Ignition 2",
          "time_offset": 10.4,
          "open_valves": [
            "AV_3",
            "IGN_2",
            "IGN_1",
            "BRAYPWR_1"
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
            "BRAYPWR_1"
          ],
          "is_terminal_count": false
        },
        {
          "name": "Main Valves",
          "time_offset": 10.0,
          "open_valves": [
            "AV_3",
            "IGN_1",
            "BRAYPWR_1"
          ],
          "is_terminal_count": false
        },
        {
          "name": "Ignition 2",
          "time_offset": 10.4,
          "open_valves": [
            "AV_3",
            "IGN_1",
            "IGN_2",
            "BRAYPWR_1"
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
    },
    {
      "id": "calc_1946c30a",
      "label": "Ox Density (N2O)",
      "role": "custom",
      "unit": "kg/m^3",
      "expression": "PropsSI('D','T',TC1+273.15,'P',P1*6894.76,'N2O')",
      "constants": {},
      "enabled": true
    }
  ],
  "actuation_plans": [
    {
      "id": "act_f350bc2e",
      "name": "Plan 1",
      "steps": []
    }
  ]
}