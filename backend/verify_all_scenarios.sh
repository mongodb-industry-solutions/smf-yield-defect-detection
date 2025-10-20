#!/bin/bash

API_BASE="http://localhost:8000"

echo "============================================"
echo "Verifying All Scenarios - Supervisor Agent"
echo "============================================"

# Scenario 1: Gradual Drift
ALERT_ID_1="ALT-SCENARIO-20251020100839-68f5bccfd9e76f0b841fd17a"
echo -e "\n1. GRADUAL DRIFT"
echo "   Alert ID: $ALERT_ID_1"

ALERT_1=$(curl -s "$API_BASE/alerts/$ALERT_ID_1")
HAS_SUPERVISOR_1=$(echo "$ALERT_1" | jq -r '.alert.supervisor_agent_analysis != null')
RECOMMENDATIONS_1=$(echo "$ALERT_1" | jq -r '.alert.supervisor_agent_analysis.llm_synthesis.recommendations | length')
CONFIDENCE_1=$(echo "$ALERT_1" | jq -r '.alert.supervisor_agent_analysis.llm_synthesis.overall_confidence')
EXEC_TIME_1=$(echo "$ALERT_1" | jq -r '.alert.supervisor_agent_analysis.execution_time_ms')

if [ "$HAS_SUPERVISOR_1" == "true" ]; then
    echo "   ✅ Supervisor analysis: SAVED"
    echo "   📊 Recommendations: $RECOMMENDATIONS_1"
    echo "   🎯 Confidence: $CONFIDENCE_1"
    echo "   ⏱️  Execution time: ${EXEC_TIME_1}ms"
else
    echo "   ❌ Supervisor analysis: MISSING"
fi

# Scenario 2: Sudden Spike
ALERT_ID_2="ALT-SCENARIO-20251020101340-68f5bdfcd9e76f0b841fd1ff"
echo -e "\n2. SUDDEN SPIKE"
echo "   Alert ID: $ALERT_ID_2"

ALERT_2=$(curl -s "$API_BASE/alerts/$ALERT_ID_2")
HAS_SUPERVISOR_2=$(echo "$ALERT_2" | jq -r '.alert.supervisor_agent_analysis != null')
RECOMMENDATIONS_2=$(echo "$ALERT_2" | jq -r '.alert.supervisor_agent_analysis.llm_synthesis.recommendations | length')
CONFIDENCE_2=$(echo "$ALERT_2" | jq -r '.alert.supervisor_agent_analysis.llm_synthesis.overall_confidence')
EXEC_TIME_2=$(echo "$ALERT_2" | jq -r '.alert.supervisor_agent_analysis.execution_time_ms')

if [ "$HAS_SUPERVISOR_2" == "true" ]; then
    echo "   ✅ Supervisor analysis: SAVED"
    echo "   📊 Recommendations: $RECOMMENDATIONS_2"
    echo "   🎯 Confidence: $CONFIDENCE_2"
    echo "   ⏱️  Execution time: ${EXEC_TIME_2}ms"
else
    echo "   ❌ Supervisor analysis: MISSING"
fi

# Scenario 3: Oscillating Pattern
ALERT_ID_3="ALT-SCENARIO-20251020101557-68f5be85d9e76f0b841fd284"
echo -e "\n3. OSCILLATING PATTERN"
echo "   Alert ID: $ALERT_ID_3"

ALERT_3=$(curl -s "$API_BASE/alerts/$ALERT_ID_3")
HAS_SUPERVISOR_3=$(echo "$ALERT_3" | jq -r '.alert.supervisor_agent_analysis != null')
RECOMMENDATIONS_3=$(echo "$ALERT_3" | jq -r '.alert.supervisor_agent_analysis.llm_synthesis.recommendations | length')
CONFIDENCE_3=$(echo "$ALERT_3" | jq -r '.alert.supervisor_agent_analysis.llm_synthesis.overall_confidence')
EXEC_TIME_3=$(echo "$ALERT_3" | jq -r '.alert.supervisor_agent_analysis.execution_time_ms')

if [ "$HAS_SUPERVISOR_3" == "true" ]; then
    echo "   ✅ Supervisor analysis: SAVED"
    echo "   📊 Recommendations: $RECOMMENDATIONS_3"
    echo "   🎯 Confidence: $CONFIDENCE_2"
    echo "   ⏱️  Execution time: ${EXEC_TIME_3}ms"
else
    echo "   ❌ Supervisor analysis: MISSING"
fi

# Summary
echo -e "\n============================================"
echo "SUMMARY: SUPERVISOR AGENT VERIFICATION"
echo "============================================"

TOTAL_SCENARIOS=3
SUCCESSFUL=0

if [ "$HAS_SUPERVISOR_1" == "true" ]; then ((SUCCESSFUL++)); fi
if [ "$HAS_SUPERVISOR_2" == "true" ]; then ((SUCCESSFUL++)); fi
if [ "$HAS_SUPERVISOR_3" == "true" ]; then ((SUCCESSFUL++)); fi

echo "Total Scenarios: $TOTAL_SCENARIOS"
echo "Successful: $SUCCESSFUL"
echo "Failed: $((TOTAL_SCENARIOS - SUCCESSFUL))"

if [ $SUCCESSFUL -eq $TOTAL_SCENARIOS ]; then
    echo -e "\n🎉 ALL SCENARIOS PASSED!"
    echo "✅ All supervisor agent analyses saved to MongoDB"
else
    echo -e "\n⚠️  SOME SCENARIOS FAILED"
fi

echo -e "\nAverage Confidence: $(echo "scale=2; ($CONFIDENCE_1 + $CONFIDENCE_2 + $CONFIDENCE_3) / 3" | bc)"
echo "Total Recommendations Generated: $((RECOMMENDATIONS_1 + RECOMMENDATIONS_2 + RECOMMENDATIONS_3))"
