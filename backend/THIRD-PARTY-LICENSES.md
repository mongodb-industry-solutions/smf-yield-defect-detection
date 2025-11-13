# Third-Party Licenses - Backend

This document contains the licenses for all third-party packages used in the backend application.

Generated on: 2025-11-13

---

## Python Packages

### pymongo (>=4.10.1)
- **License:** Apache License 2.0
- **Repository:** https://github.com/mongodb/mongo-python-driver
- **Description:** Python driver for MongoDB

### motor (>=3.3.2)
- **License:** Apache License 2.0
- **Repository:** https://github.com/mongodb/motor
- **Description:** Async Python driver for MongoDB

### python-dotenv (>=1.0.1)
- **License:** BSD-3-Clause
- **Repository:** https://github.com/theskumar/python-dotenv
- **Description:** Read key-value pairs from .env file

### fastapi (>=0.115.4)
- **License:** MIT License
- **Repository:** https://github.com/tiangolo/fastapi
- **Description:** Modern web framework for building APIs

### uvicorn (>=0.32.0)
- **License:** BSD-3-Clause
- **Repository:** https://github.com/encode/uvicorn
- **Description:** ASGI web server implementation

### boto3 (>=1.35.70)
- **License:** Apache License 2.0
- **Repository:** https://github.com/boto/boto3
- **Description:** AWS SDK for Python

### botocore (>=1.35.70)
- **License:** Apache License 2.0
- **Repository:** https://github.com/boto/botocore
- **Description:** Low-level interface to AWS services

### tqdm (>=4.67.1)
- **License:** MIT License, MPL-2.0
- **Repository:** https://github.com/tqdm/tqdm
- **Description:** Progress bar library

### pandas (>=2.2.3)
- **License:** BSD-3-Clause
- **Repository:** https://github.com/pandas-dev/pandas
- **Description:** Data analysis and manipulation tool

### numpy (>=1.24.0)
- **License:** BSD-3-Clause
- **Repository:** https://github.com/numpy/numpy
- **Description:** Fundamental package for scientific computing

### Pillow (>=10.0.0)
- **License:** HPND (Historical Permission Notice and Disclaimer)
- **Repository:** https://github.com/python-pillow/Pillow
- **Description:** Python Imaging Library

### langchain-core (>=0.3.0)
- **License:** MIT License
- **Repository:** https://github.com/langchain-ai/langchain
- **Description:** Core components for LangChain

### langchain-aws (>=0.2.15)
- **License:** MIT License
- **Repository:** https://github.com/langchain-ai/langchain-aws
- **Description:** AWS integrations for LangChain

### langchain-mongodb (>=0.5.0)
- **License:** MIT License
- **Repository:** https://github.com/langchain-ai/langchain-mongodb
- **Description:** MongoDB integrations for LangChain

### langgraph (>=0.3.5)
- **License:** MIT License
- **Repository:** https://github.com/langchain-ai/langgraph
- **Description:** Library for building stateful multi-actor applications

### grandalf (>=0.8)
- **License:** GPL-2.0 or EPL-1.0
- **Repository:** https://github.com/bdcht/grandalf
- **Description:** Graph and drawing algorithms framework

### langgraph-checkpoint-mongodb (>=0.1.1)
- **License:** MIT License
- **Repository:** https://github.com/langchain-ai/langgraph-checkpoint-mongodb
- **Description:** MongoDB checkpointing for LangGraph

### annotated-types (>=0.7.0)
- **License:** MIT License
- **Repository:** https://github.com/annotated-types/annotated-types
- **Description:** Reusable constraint types

### websockets (>=12.0)
- **License:** BSD-3-Clause
- **Repository:** https://github.com/python-websockets/websockets
- **Description:** WebSocket client and server library

### voyageai (>=0.2.3)
- **License:** Apache License 2.0
- **Repository:** https://github.com/voyage-ai/voyageai-python
- **Description:** Python client for Voyage AI API

### aiohttp (>=3.9.0)
- **License:** Apache License 2.0
- **Repository:** https://github.com/aio-libs/aiohttp
- **Description:** Async HTTP client/server framework

### websocket-client (>=1.8.0)
- **License:** Apache License 2.0
- **Repository:** https://github.com/websocket-client/websocket-client
- **Description:** WebSocket client library

### langgraph-supervisor (>=0.0.29)
- **License:** MIT License
- **Repository:** https://github.com/langchain-ai/langgraph-supervisor
- **Description:** Supervisor pattern for LangGraph

### langchain-anthropic (>=0.3.21)
- **License:** MIT License
- **Repository:** https://github.com/langchain-ai/langchain-anthropic
- **Description:** Anthropic Claude integrations for LangChain

---

## License Texts

### Apache License 2.0
```
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
```

### MIT License
```
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

### BSD-3-Clause License
```
Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice,
   this list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

3. Neither the name of the copyright holder nor the names of its contributors
   may be used to endorse or promote products derived from this software
   without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
```

---

## Notes

This file lists the direct dependencies of the backend application. Each dependency may have its own dependencies (transitive dependencies) with their own licenses. For complete license information, please refer to the individual package repositories.

To verify or update this information, you can use tools like:
- `pip-licenses` - Generate licenses list: `pip install pip-licenses && pip-licenses --format=markdown`
- Check individual package metadata: `pip show <package-name>`
