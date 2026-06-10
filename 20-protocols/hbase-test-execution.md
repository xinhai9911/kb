---
title: HBase Decoder TPR 字段测试执行计划
tags: [protocol, hbase, test-plan, active]
created: 2026-06-10
updated: 2026-06-10
status: active
source: Q:\AI\hbase_test_execution_plan.md
---


# HBase Decoder TPR Field Test Execution Plan

## Pre-Test Setup

### 1. Sync libhbase.so to Test Environment
```bash
# Wait for remote-builder to complete
# Then sync the built library to test environment
scp ./output/edisk/root/usr/local/lib/libhbase.so \
  lujun2@testhost:/home/lujun2/test_falcon_run_osms/falcon-database-protocol/output/edisk/root/usr/local/lib/
```

### 2. Update falcon.yaml Configuration
Add HBase protocol support to falcon.yaml:
```yaml
# Example configuration structure (to be verified)
falcon:
  protocols:
    - name: hbase
      enabled: true
      ports: [16000, 16010, 16020, 16030]  # Default HBase ports
      decoder_lib: libhbase.so
```

**Note**: The actual configuration format needs to be verified from existing examples or documentation.

### 3. Verify Test Environment
```bash
# Check if falcon service is running
ps aux | grep falcon

# Check if libhbase.so is in place
ls -la /home/lujun2/test_falcon_run_osms/falcon-database-protocol/output/edisk/root/usr/local/lib/libhbase.so

# Verify configuration
cat /path/to/falcon.yaml | grep -A 10 "hbase"
```

## Test Execution

### 4. Run Decoder with Test Pcap
```bash
# Command structure (to be updated based on actual falcon testing tools)
falcon_decode_tool --pcap /path/to/dbtype@hbase-dst_ip@10.66.241.5.pcap \
                   --protocol hbase \
                   --output /tmp/hbase_test_results.json
```

### 5. Verify TPR Field Extraction

#### DBSql Fields (Transaction-level)
| Field ID | Field Name | Expected Value | Extracted Value | Status | Notes |
|----------|------------|----------------|-----------------|--------|-------|
| 18 | dbUserName | | | ✅/❌ | |
| 20 | sqlStatement | | | ✅/❌ | Should contain HBase operation (Get, Put, Scan, etc.) |
| 28 | toolName | | | ✅/❌ | e.g., "HBase Shell", "Java API" |
| 29 | actionType | | | ✅/❌ | From CSV: 1=DDL, 2=DML, 5=Admin, 6=Function |
| 30 | actionSubType | | | ✅/❌ | Specific operation ID |
| 38 | dbHost | | | ✅/❌ | Database server hostname/IP |
| 39 | clientHost | | | ✅/❌ | Client hostname/IP |
| 40 | dbName | | | ✅/❌ | Namespace or table name |
| 41 | tableNames | | | ✅/❌ | Comma-separated table names |

#### DBSession Fields (Session-level)
| Field ID | Field Name | Expected Value | Extracted Value | Status | Notes |
|----------|------------|----------------|-----------------|--------|-------|
| 1041 | dbUserName | | | ✅/❌ | |
| 1043 | toolName | | | ✅/❌ | |
| 1048 | dbHost | | | ✅/❌ | |
| 1049 | clientHost | | | ✅/❌ | |
| 1055 | dbName | | | ✅/❌ | |

#### DBInfo Fields (Database info)
| Field ID | Field Name | Expected Value | Extracted Value | Status | Notes |
|----------|------------|----------------|-----------------|--------|-------|
| 2064 | dbVer | | | ✅/❌ | HBase version |
| 2065 | dbName | | | ✅/❌ | |
| 2068 | dbHost | | | ✅/❌ | |

### 6. Calculate Success Rate
```
Success Rate = (Number of successfully extracted fields / Total expected fields) × 100%

Target: ≥ 90% success rate for test to PASS
```

## Test Cases

### Test Case 1: Basic HBase Operations
- **Pcap**: `dbtype@hbase-dst_ip@10.66.241.5.pcap`
- **Operations to verify**: Get, Put, Scan, CreateTable, DeleteTable
- **Expected**: All TPR fields populated correctly

### Test Case 2: Edge Cases
- Empty table name
- Special characters in table name
- Large payloads
- Multiple operations in single pcap

## Post-Test Analysis

### 7. Generate Test Report
```bash
# Create report with:
# - Total transactions processed
# - Field extraction success rate per field
# - Examples of correctly extracted fields
# - Examples of missing/incorrect fields
# - Recommendations for fixes
```

### 8. Report Template
```
HBase Decoder TPR Field Test Report
====================================
Test Date: [DATE]
Test Environment: [ENV]
Pcap File: dbtype@hbase-dst_ip@10.66.241.5.pcap
libhbase.so Version: [VERSION]

## Summary
- Total Transactions: [N]
- DBSql Fields Success Rate: [%]
- DBSession Fields Success Rate: [%]
- DBInfo Fields Success Rate: [%]
- Overall Success Rate: [%]

## Detailed Results
[Table with per-field results]

## Issues Found
[List any bugs or missing extractions]

## Recommendations
[Suggestions for improvement]
```

## Next Steps
1. Wait for remote-builder to provide libhbase.so
2. Verify test environment setup
3. Execute tests
4. Generate report
5. Send results to team-lead
