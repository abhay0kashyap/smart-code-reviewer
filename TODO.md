# AI Fix System - Implementation Plan

## Phase 1: Convert Backend to FastAPI
- [ ] Install FastAPI and uvicorn
- [ ] Create new FastAPI app in backend/
- [ ] Convert /run endpoint
- [ ] Convert /ai-fix endpoint with proper prompt format

## Phase 2: Fix AI-Fix Endpoint
- [ ] Extract: code, error_type, error_message, traceback from request
- [ ] Build AI prompt exactly as specified
- [ ] Proper OpenAI API call with latest SDK
- [ ] Handle exceptions and return proper JSON error
- [ ] Never cache/globally store fixes

## Phase 3: Fix Frontend
- [ ] Update fetch to send correct payload format
- [ ] Add loading spinner handling
- [ ] Handle success/error response properly
- [ ] Add console.log debugging

## Phase 4: Testing
- [ ] Test /run endpoint
- [ ] Test /ai-fix endpoint with valid code
- [ ] Test error handling when OpenAI fails
- [ ] Verify full flow from UI

