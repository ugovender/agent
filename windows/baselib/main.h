#define _CRT_SECURE_NO_WARNINGS

#include <windows.h>
#include <Aclapi.h>
#include <shlobj.h>
#include <vector>
/*
This Source Code Form is subject to the terms of the Mozilla
Public License, v. 2.0. If a copy of the MPL was not distributed
with this file, You can obtain one at http://mozilla.org/MPL/2.0/.
*/
#include <algorithm>

using namespace std;

#ifndef MAIN_H_
#define MAIN_H_

extern "C"{
  
__declspec(dllexport) BOOL taskKill(int pid);
__declspec(dllexport) BOOL isTaskRunning(int pid);  
__declspec(dllexport) void setFilePermissionEveryone(LPCTSTR FileName);

}


#endif /* MAIN_H_ */

