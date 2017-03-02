/*
This Source Code Form is subject to the terms of the Mozilla
Public License, v. 2.0. If a copy of the MPL was not distributed
with this file, You can obtain one at http://mozilla.org/MPL/2.0/.
*/

#define _CRT_SECURE_NO_DEPRECATE
#include <windows.h>
#include <string>
#include <tchar.h>
#include <fstream>
#include <UserEnv.h>

#pragma comment(lib,"UserEnv.lib")
#pragma comment(lib,"Shell32.lib")
#pragma comment(lib,"Advapi32.lib")
#pragma comment(lib,"User32.lib")

#pragma warning(disable : 4995)

using namespace std;


wstring getDWAgentPath(){
	wchar_t strPathName[_MAX_PATH];
	GetModuleFileNameW(NULL, strPathName, _MAX_PATH);
	wstring newPath(strPathName);
	int fpos = newPath.find_last_of('\\');
	if (fpos != -1)
		newPath = newPath.substr(0,(fpos));
	fpos = newPath.find_last_of('\\');
	if (fpos != -1)
		newPath = newPath.substr(0,(fpos));
	return newPath;
}

BOOL isRunAsAdmin(){
    BOOL fIsRunAsAdmin = FALSE;
    DWORD dwError = ERROR_SUCCESS;
    PSID pAdministratorsGroup = NULL;
    SID_IDENTIFIER_AUTHORITY NtAuthority = SECURITY_NT_AUTHORITY;
    if (!AllocateAndInitializeSid(
        &NtAuthority,
        2,
        SECURITY_BUILTIN_DOMAIN_RID,
        DOMAIN_ALIAS_RID_ADMINS,
        0, 0, 0, 0, 0, 0,
        &pAdministratorsGroup))
    {
        dwError = GetLastError();
        goto Cleanup;
    }

    if (!CheckTokenMembership(NULL, pAdministratorsGroup, &fIsRunAsAdmin)){
        dwError = GetLastError();
        goto Cleanup;
    }

Cleanup:
    if (pAdministratorsGroup){
        FreeSid(pAdministratorsGroup);
        pAdministratorsGroup = NULL;
    }
    if (ERROR_SUCCESS != dwError){
        throw dwError;
    }
    return fIsRunAsAdmin;
}

BOOL existsFile(wstring fileName) {
	ifstream ifile(fileName);
    if (ifile!=NULL){
		ifile.close();
		return true;
	}else{
		return false;
	}
}

bool deleteDir(const wchar_t *path){
	bool bret=true;
    WIN32_FIND_DATAW FindFileData;
    HANDLE hFind;
    DWORD Attributes;
    wchar_t str[MAX_PATH];
	wcscpy(str,path);
	wcscat(str,L"\\*.*");
    hFind = FindFirstFileW(str, &FindFileData);
    do{
        if (wcscmp(FindFileData.cFileName, L".") != 0 && wcscmp(FindFileData.cFileName, L"..") != 0)
        {
            wcscpy(str, path);
            wcscat(str,L"\\");
            wcscat (str,FindFileData.cFileName);
            Attributes = GetFileAttributesW(str);
			if (Attributes & FILE_ATTRIBUTE_DIRECTORY){
                if (!deleteDir(str)){
					bret=false;
					break;
				}
            }else{
				if (!DeleteFileW(str)){
					bret=false;
					break;
				}
            }
        }
    }while(FindNextFileW(hFind, &FindFileData));
    FindClose(hFind);
    RemoveDirectoryW(path);
    return bret;
}

void startRemove(wstring dwPath){
	STARTUPINFOW siStartupInfo;
	PROCESS_INFORMATION piProcessInfo;
	BOOL bRunAsUser=FALSE;
	HANDLE hUserTokenDup;
	DWORD dwCreationFlags;
	LPVOID pEnv =NULL;

	wchar_t szTempPath[MAX_PATH];
	GetTempPathW(MAX_PATH,szTempPath);
	wchar_t szDestPath[MAX_PATH];
	wcscpy(szDestPath,szTempPath);
	wcscat(szDestPath, L"dwaglnc.exe");
	wchar_t szSrcPath[MAX_PATH];
	wcscpy(szSrcPath, dwPath.c_str());
	wcscat(szSrcPath, L"\\native\\dwaglnc.exe");
	DeleteFileW(szDestPath);
	CopyFileW(szSrcPath, szDestPath, false);
	wchar_t cmd[(MAX_PATH * 2)+100];
	wcscpy(cmd,szDestPath);
	wcscat(cmd, L" remove \"");
	wcscat(cmd, dwPath.c_str());
	wcscat(cmd, L"\"");


	dwCreationFlags = NORMAL_PRIORITY_CLASS|CREATE_NO_WINDOW;
	ZeroMemory(&siStartupInfo, sizeof(STARTUPINFO));
	siStartupInfo.cb= sizeof(STARTUPINFO);
	siStartupInfo.lpReserved=NULL;
	siStartupInfo.lpDesktop = L"winsta0\\default";
	siStartupInfo.lpTitle=L"DWAgent Remover";
	siStartupInfo.dwX=0;
	siStartupInfo.dwY=0;
	siStartupInfo.dwXSize=0;
	siStartupInfo.dwYSize=0;
	siStartupInfo.dwXCountChars=0;
	siStartupInfo.dwYCountChars=0;
	siStartupInfo.dwFillAttribute=0;
	siStartupInfo.wShowWindow=0;

	ZeroMemory(&piProcessInfo, sizeof(piProcessInfo));
	HANDLE procHandle = GetCurrentProcess();
	DWORD dwSessionId = WTSGetActiveConsoleSessionId();
	if (dwSessionId) {
		HANDLE hPToken;
		if (!OpenProcessToken(procHandle, TOKEN_DUPLICATE, &hPToken) == 0) {
			if (DuplicateTokenEx(hPToken,MAXIMUM_ALLOWED,0,SecurityImpersonation,TokenPrimary,&hUserTokenDup) != 0) {
				if (SetTokenInformation(hUserTokenDup,(TOKEN_INFORMATION_CLASS) TokenSessionId,&dwSessionId,sizeof (dwSessionId)) != 0) {
					if(CreateEnvironmentBlock(&pEnv,hUserTokenDup,TRUE)){
						dwCreationFlags|=CREATE_UNICODE_ENVIRONMENT;
					}else{
						pEnv=NULL;
					}
					bRunAsUser=TRUE;
				}
			}
		}
	}
	if (bRunAsUser){
		CreateProcessAsUserW(
			hUserTokenDup,          
			NULL,              
			cmd,     
			NULL,              
			NULL,              
			FALSE,             
			dwCreationFlags,  
			pEnv,             
			szTempPath,       
			&siStartupInfo,   
			&piProcessInfo    
			);
	}else{
		CreateProcessW(NULL, 
						cmd, 
						NULL,
						NULL,
						FALSE,
						dwCreationFlags,
						NULL,
						szTempPath, // Working directory
						&siStartupInfo,
						&piProcessInfo);
	}
}

int WINAPI WinMain(HINSTANCE hInstance,
                   HINSTANCE hPrevIn,
                   LPSTR lpCmdLine,
                   int nCmdShow){

	LPWSTR *szArgList;
    int argCount;
	szArgList = CommandLineToArgvW(GetCommandLineW(), &argCount);
	if( argCount > 0){
		LPWSTR scommand=szArgList[1];
		wstring dwPath = getDWAgentPath();
		wstring cmd=L"";
		if (wcscmp(scommand,L"monitor")==0){
			cmd=L"monitor.pyc window";
			ShellExecuteW(GetDesktopWindow(), L"open", L"runtime\\dwagent.exe", cmd.c_str(), dwPath.c_str() , SW_SHOW);
		}else if (wcscmp(scommand,L"systray")==0){
			cmd=L"monitor.pyc systray";
			ShellExecuteW(GetDesktopWindow(), L"open", L"runtime\\dwagent.exe", cmd.c_str(), dwPath.c_str() , SW_SHOW);
		}else if (wcscmp(scommand,L"configure")==0){
			cmd=L"configure.pyc";
			ShellExecuteW(GetDesktopWindow(), L"open", L"runtime\\dwagent.exe", cmd.c_str(), dwPath.c_str() , SW_SHOW);
		}else if (wcscmp(scommand,L"uninstallAsAdimn")==0){
			SHELLEXECUTEINFOW ShExecInfo = {0};
			ShExecInfo.cbSize = sizeof(SHELLEXECUTEINFOW);
			ShExecInfo.fMask = SEE_MASK_NOCLOSEPROCESS;
			ShExecInfo.hwnd = NULL;
			ShExecInfo.lpVerb = NULL;
			ShExecInfo.lpFile = L"runtime\\dwagent.exe";
			ShExecInfo.lpParameters = L"installer.pyc uninstall";
			ShExecInfo.lpDirectory = dwPath.c_str();
			ShExecInfo.nShow = SW_SHOW;
			ShExecInfo.hInstApp = NULL;
			ShellExecuteExW(&ShExecInfo);
			WaitForSingleObject(ShExecInfo.hProcess,INFINITE);
			//Elimina cartella lanciando l'applicazione da temp
			wstring fln = dwPath;
			fln.append(L"\\").append(L"agent.uninstall");
			if (existsFile(fln)){
				startRemove(dwPath);
			}
		}else if (wcscmp(scommand,L"uninstall")==0){
			//Rilancia L'Applicazione come Amministratore
			SHELLEXECUTEINFOW ShExecInfo = {0};
			ShExecInfo.cbSize = sizeof(SHELLEXECUTEINFOW);
			ShExecInfo.fMask = SEE_MASK_NOCLOSEPROCESS;
			ShExecInfo.hwnd = NULL;
			if (isRunAsAdmin()){
				ShExecInfo.lpVerb  = NULL;
			}else{
				ShExecInfo.lpVerb  = L"runas";
			}
			ShExecInfo.lpFile = L"native\\dwaglnc.exe";
			ShExecInfo.lpParameters = L"uninstallAsAdimn";
			ShExecInfo.lpDirectory = dwPath.c_str();
			ShExecInfo.nShow = SW_SHOW;
			ShExecInfo.hInstApp = NULL;
			ShellExecuteExW(&ShExecInfo);
		}else if (wcscmp(scommand,L"remove")==0){
			if (!wcscmp(szArgList[2],L"")==0){
				Sleep(2000);
				deleteDir(szArgList[2]);
			}
		}
		LocalFree(szArgList);
	}
    return 0;
}

