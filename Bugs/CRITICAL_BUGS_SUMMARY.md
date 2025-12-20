# 🐛 KrishiMitra Pipeline - Critical Bugs Summary
**Test Date:** 2025-11-17
**Tests Run:** 5 comprehensive tests covering all agent types

---

## ❌ CRITICAL BUGS FOUND

### **BUG #1: Misclassification of Explicit Parameter Queries**
**Severity:** 🔴 **CRITICAL**
**Test:** `N=90 P=40 K=40 temp=25 humidity=80 ph=6 rainfall=200`

**Expected Behavior:**
- Should classify as `crop_recommendation` (all 7 parameters provided)
- Should extract params → call crop model → recommend crop (likely rice/wheat based on params)

**Actual Behavior:**
- ❌ Classified as `multi_agent` → `fertilizer_agent` + `weather_agent`
- Fertilizer agent extracted NPK but asked for soil_type + crop_type
- Weather agent asked for location
- **User gets 2 clarification questions instead of crop recommendation**

**Root Cause:**
- Supervisor's query classifier doesn't recognize explicit parameter patterns as crop queries
- NPK values trigger fertilizer intent instead of crop intent

**Impact:** HIGH - Users providing complete data get clarification requests

---

### **BUG #2: Crop Preference Detection Not Triggering**
**Severity:** 🔴 **CRITICAL**
**Test:** `I want to grow wheat in my farm`

**Expected Behavior:**
- `_detect_user_crop_preference()` should detect "wheat"
- Should acknowledge preference: "You mentioned wanting to grow wheat. That's a great choice!"
- Skip crop recommendation model

**Actual Behavior:**
- ❌ Preference detection did NOT fire
- Ran crop_agent normallow → extracted zero parameters → used defaults → recommended **JUTE**
- User's explicit intent completely ignored

**Root Cause:**
- The detection logic exists but the regex pattern may not match "want to grow wheat"
- Possible issue: Pattern looks for "want to grow" but matches greedy word boundary incorrectly

**Impact:** HIGH - User preferences ignored, irrelevant recommendations given

---

### **BUG #3: Location-Aware Crop Recommendation Fails**
**Severity:** 🔴 **CRITICAL**
**Test:** `What crops grow well in Bangalore?`

**Expected Behavior:**
- Extract location "Bangalore"
- Infer climate params: temp=25°C, humidity=65%, rainfall=100mm
- Use inferred params → recommend suitable crops (tomato, beans, leafy greens)

**Actual Behavior:**
- ❌ LLM extracted zero parameters
- Applied all 7 defaults (N=50, P=50, K=50, temp=25, humidity=65, ph=6.5, rainfall=100)
- Recommended **JUTE** (which is wrong for Bangalore)
- Completely ignored "Bangalore" location

**Root Cause:**
- LLM parameter extraction doesn't infer climate from location names
- No regional climate database lookup
- Defaults always produce jute recommendation

**Impact:** CRITICAL - Location-specific queries return wrong recommendations

---

### **BUG #4: Contextual Reference Resolution Fails**
**Severity:** 🔴 **CRITICAL**
**Test Sequence:**
1. `What crops grow well in Bangalore?` → Session created with "Bangalore" mentioned
2. `What is the weather there?` (same session) → Should resolve "there" to "Bangalore"

**Expected Behavior:**
- `_resolve_location_references()` should check:
  1. `collected_findings` from previous queries
  2. `conversation_history` for "Bangalore"
- Resolve "there" → "Bangalore"
- Fetch weather for Bangalore

**Actual Behavior:**
- ❌ Detected contextual reference ("there") ✅
- ❌ Could not resolve reference
- Logged: `weather_agent: Could not resolve contextual reference`
- Asked user for clarification: "Which location would you like weather information for?"

**Root Cause Analysis:**
1. Previous query only ran `crop_agent`, NOT `weather_agent`
2. `collected_findings` has no `weather_agent` entry
3. Bangalore mentioned in query but NOT saved to `user_context["location"]`
4. `conversation_history` check pattern failed

**Impact:** CRITICAL - Multi-turn conversations broken, contextual references don't work

---

### **BUG #5: Supervisor Doesn't Store Location in user_context**
**Severity:** 🟠 **HIGH**
**Related to:** Bug #3, Bug #4

**Problem:**
- When user mentions location in query (e.g., "Bangalore"), supervisor doesn't extract and store it in `user_context["location"]`
- Location information lost after query completes
- Future queries can't use it

**Expected:**
- Supervisor should extract location mentions → store in `user_context["location"]` → persist in session
- Enables contextual reference resolution

**Actual:**
- Location mentioned but not saved anywhere except conversation_history

**Impact:** HIGH - Breaks multi-turn location-aware conversations

---

### **BUG #6: collected_findings Doesn't Persist Across Supervisor Cycles**
**Severity:** 🟠 **HIGH**
**Test:** Multi-agent queries

**Problem:**
- When supervisor routes to multiple agents sequentially, `collected_findings` doesn't accumulate correctly
- Second supervisor call shows `executed=[]` instead of `executed=['first_agent']`
- Losing execution history mid-workflow

**Example from logs:**
```
Supervisor.run() called - plan=['weather_agent'], executed=['fertilizer_agent']
[fertilizer_agent executes]
Supervisor.run() called - plan=[], executed=[]  ← SHOULD BE ['fertilizer_agent']!
```

**Impact:** HIGH - Inter-agent state sharing breaks, agents can't see previous findings

---

### **BUG #7: Supervisor Re-classifies Query Every Time**
**Severity:** 🟡 **MEDIUM**
**Test:** All multi-turn tests

**Problem:**
- Every supervisor cycle runs full query classification (1-1.5 seconds)
- Even for follow-up queries in same session
- Wastes time and API calls

**Example:**
- Turn 1: "What is the weather there?" → Classify (1.2s)
- Supervisor routes to weather_agent
- Supervisor called again → **Re-classifies same query** (another 1.2s!)

**Impact:** MEDIUM - Unnecessary latency (2x classification per query)

---

## ✅ WORKING CORRECTLY

### **Test 4: Fertilizer Recommendation** ✅
- Query: `Which fertilizer for wheat in black soil?`
- Extracted: soil_type=black, crop_type=wheat
- Applied defaults for missing params
- Predicted: **Urea** ✅ CORRECT
- Status: **WORKING**

### **Test 5: General RAG** ✅
- Query: `What is crop rotation?`
- Retrieved chunks from Pinecone
- Generated answer using Gemini
- Status: **WORKING**

---

## 🔧 RECOMMENDED FIX PRIORITY

### **P0 - CRITICAL (Fix Immediately)**
1. ✅ **Bug #1** - Add pattern detection for explicit parameters → route to crop_agent
2. ✅ **Bug #2** - Fix crop preference detection regex patterns
3. ✅ **Bug #3** - Add location-to-climate inference for crop_agent
4. ✅ **Bug #4** - Fix contextual reference resolution to check conversation_history properly

### **P1 - HIGH (Fix This Week)**
5. ⚠️ **Bug #5** - Supervisor extracts and stores location in user_context
6. ⚠️ **Bug #6** - Fix collected_findings persistence across supervisor cycles

### **P2 - MEDIUM (Fix Next Sprint)**
7. ⚠️ **Bug #7** - Cache classification results, don't re-classify same query

---

## 📊 TEST RESULTS SUMMARY

| Test # | Query | Expected Agent | Actual Agent(s) | Result | Bug # |
|--------|-------|---------------|-----------------|--------|-------|
| 1 | N=90 P=40 K=40... | crop_agent | fertilizer + weather | ❌ FAIL | #1 |
| 2 | I want to grow wheat | crop_agent (preference) | crop_agent (defaults→jute) | ❌ FAIL | #2 |
| 3 | Crops in Bangalore | crop_agent (location-aware) | crop_agent (defaults→jute) | ❌ FAIL | #3 |
| 3B | Weather there? | weather_agent (Bangalore) | weather_agent (clarification) | ❌ FAIL | #4 |
| 4 | Fertilizer for wheat | fertilizer_agent | fertilizer_agent | ✅ PASS | - |
| 5 | What is crop rotation | general_rag_agent | general_rag_agent | ✅ PASS | - |

**Pass Rate: 33% (2/6 tests passed)**

---

## 🎯 NEXT STEPS

1. Fix P0 bugs (#1-4) in `crop_agent.py`, `supervisor.py`, `weather_agent.py`
2. Add location extraction to supervisor
3. Fix state persistence in orchestrator
4. Re-run all 6 tests
5. Target: **100% pass rate** before deployment

---

## 📝 NOTES

- Bugs #1-4 are **BLOCKING** for production
- Users will get incorrect recommendations with current code
- Multi-turn conversations completely broken
- Explicit data from users is ignored

**The fixes I implemented earlier (Bug #1, #2, #3, #8, #10) are NOT WORKING in the actual pipeline!**
