/*
This Source Code Form is subject to the terms of the Mozilla
Public License, v. 2.0. If a copy of the MPL was not distributed
with this file, You can obtain one at http://mozilla.org/MPL/2.0/.
*/

#include "main.h"

__declspec(dllexport) BOOL taskKill(int pid) {
	DWORD dwDesiredAccess = PROCESS_TERMINATE;
    BOOL  bInheritHandle  = FALSE;
    HANDLE hProcess = OpenProcess(dwDesiredAccess, bInheritHandle, pid);
    if (hProcess == NULL)
        return FALSE;
	DWORD uExitCode = 0;
    GetExitCodeProcess(hProcess, &uExitCode);
    BOOL result = TerminateProcess(hProcess, uExitCode);

    CloseHandle(hProcess);
	return result;
}

__declspec(dllexport) BOOL isTaskRunning(int pid) {
	DWORD dwDesiredAccess = SYNCHRONIZE;
    BOOL  bInheritHandle  = FALSE;
	HANDLE hProcess = OpenProcess(dwDesiredAccess, bInheritHandle, pid);
    if (hProcess == NULL)
        return FALSE;
	DWORD ret = WaitForSingleObject(hProcess, 0);
	CloseHandle(hProcess);
	return ret == WAIT_TIMEOUT;
}

__declspec(dllexport) void setFilePermissionEveryone(LPCTSTR FileName){
    PSID pEveryoneSID = NULL;
    PACL pACL = NULL;
    EXPLICIT_ACCESS ea[1];
    SID_IDENTIFIER_AUTHORITY SIDAuthWorld = SECURITY_WORLD_SID_AUTHORITY;

    AllocateAndInitializeSid(&SIDAuthWorld, 1,
                     SECURITY_WORLD_RID,
                     0, 0, 0, 0, 0, 0, 0,
                     &pEveryoneSID);

    ZeroMemory(&ea, 1 * sizeof(EXPLICIT_ACCESS));
    ea[0].grfAccessPermissions = 0xFFFFFFFF;
    ea[0].grfAccessMode = GRANT_ACCESS;
    ea[0].grfInheritance= NO_INHERITANCE;
    ea[0].Trustee.TrusteeForm = TRUSTEE_IS_SID;
    ea[0].Trustee.TrusteeType = TRUSTEE_IS_WELL_KNOWN_GROUP;
    ea[0].Trustee.ptstrName  = (LPTSTR) pEveryoneSID;
	SetEntriesInAcl(1, ea, NULL, &pACL);
	PSECURITY_DESCRIPTOR pSD = (PSECURITY_DESCRIPTOR) LocalAlloc(LPTR, 
                                SECURITY_DESCRIPTOR_MIN_LENGTH); 

    InitializeSecurityDescriptor(pSD,SECURITY_DESCRIPTOR_REVISION);

    SetSecurityDescriptorDacl(pSD, 
            TRUE,
            pACL, 
            FALSE);


    SetFileSecurity(FileName, DACL_SECURITY_INFORMATION, pSD);

    if (pEveryoneSID) 
        FreeSid(pEveryoneSID);
    if (pACL) 
        LocalFree(pACL);
    if (pSD) 
        LocalFree(pSD);
}