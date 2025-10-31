#!/bin/bash

echo "🔥 TESTING 6 DOCUMENTED GREENWASHING CASES"
echo "=========================================="
echo ""

echo "Test 1/6: H&M - 100% Sustainable Fashion"
python main_langgraph.py "H&M" "H&M is committed to 100% sustainable fashion and eco-friendly materials across all collections" "Consumer Goods" | grep -A 10 "EXECUTIVE SUMMARY"
echo ""
sleep 2

echo "Test 2/6: Volkswagen - Clean Diesel (Dieselgate)"
python main_langgraph.py "Volkswagen" "Volkswagen diesel cars meet strict environmental standards and provide clean, efficient driving" "Automotive" | grep -A 10 "EXECUTIVE SUMMARY"
echo ""
sleep 2

echo "Test 3/6: Shell - Net Zero by 2050"
python main_langgraph.py "Shell" "Shell is on track to achieve net-zero emissions by 2050 through our energy transition strategy" "Energy" | grep -A 10 "EXECUTIVE SUMMARY"
echo ""
sleep 2

echo "Test 4/6: Nestlé - Sustainable Water"
python main_langgraph.py "Nestle" "Nestle ensures responsible and sustainable use of water resources in all our operations" "Consumer Goods" | grep -A 10 "EXECUTIVE SUMMARY"
echo ""
sleep 2

echo "Test 5/6: BP - Beyond Petroleum"
python main_langgraph.py "BP" "BP is transitioning beyond petroleum toward renewable energy and sustainable solutions" "Energy" | grep -A 10 "EXECUTIVE SUMMARY"
echo ""
sleep 2

echo "Test 6/6: Coca-Cola - World Without Waste"
python main_langgraph.py "Coca-Cola" "Coca-Cola will collect and recycle 100% of its packaging by 2030 through our World Without Waste initiative" "Consumer Goods" | grep -A 10 "EXECUTIVE SUMMARY"
echo ""

echo "=========================================="
echo "✅ All 6 documented greenwashing cases tested!"
