/*
This Source Code Form is subject to the terms of the Mozilla
Public License, v. 2.0. If a copy of the MPL was not distributed
with this file, You can obtain one at http://mozilla.org/MPL/2.0/.
*/
#define _CRT_SECURE_NO_DEPRECATE
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <iostream>
#include <fstream>
#include <cstdlib>
#include <aclapi.h>
#include <string>
#include <shlobj.h>
#include <time.h>
#include <Aclapi.h>
#include <shlobj.h>
#include <vector>
#include <algorithm>


using namespace std;

SERVICE_STATUS ServiceStatus;
SERVICE_STATUS_HANDLE hStatus;
STARTUPINFOW siStartupInfo;
PROCESS_INFORMATION piProcessInfo;

bool bclose = false;
bool bRunning=false;
bool brunonfly=false;
wstring logfile = L"";
wstring serviceName = L"";
wstring pidFileName = L"";
wstring startFileName = L"";
wstring stopFileName = L"";
wstring pythonPath = L"";
wstring parameters = L"";
wstring workPath = L"";

#pragma comment(lib,"Advapi32.lib")

void WINAPI ServiceMain(DWORD argc, LPWSTR *argv);
void WINAPI ServiceCtrlHandler(DWORD Opcode);

typedef bool (*FUPDATER)();
typedef void (*CallbackType)(const wchar_t*);
typedef bool (*FCALLBACKLOG)(CallbackType);

void trim(wstring& str, wchar_t c) {
    string::size_type pos = str.find_last_not_of(c);
    if (pos != string::npos) {
        str.erase(pos + 1);
        pos = str.find_first_not_of(c);
        if (pos != string::npos) str.erase(0, pos);
    } else str.erase(str.begin(), str.end());
}

void trimAll(wstring& str) {
    trim(str, ' ');
    trim(str, '\r');
    trim(str, '\n');
    trim(str, '\t');
}

wchar_t* towchar_t(wstring& str) {
    wchar_t* apps = new wchar_t[str.size() + 1];
	wcscpy(apps, str.c_str());
    return apps;
}

string tostr(char* str) {
    string tmp_str(str);
    return tmp_str;
}

void WriteToLog(const wchar_t* str) {
    if (logfile.compare(L"") != 0) {
        FILE* log;
        log = _wfopen(towchar_t(logfile), L"a+");
        if (log == NULL)
            return;

		time_t t = time(NULL);
		struct tm *tlc = localtime(&t);
		wchar_t* stm = _wasctime(tlc);
		stm[wcslen(stm)-1] = '\0';
        fwprintf(log, L"%s %s\n", stm, str);
        fclose(log);
    }
}

BOOL existsDir(wstring file){
	DWORD returnvalue;
	returnvalue = GetFileAttributesW(file.c_str());
	if(returnvalue == ((DWORD)-1)){
		return false;
	}
	else{
		return true;
	}
}

BOOL existsFileInWorkDir(wstring fileName) {
	wstring path = workPath;
	path.append(L"\\").append(fileName);
    wifstream ifile(towchar_t(path));
    if (ifile!=NULL){
		ifile.close();
		return true;
	}else{
		return false;
	}
}

BOOL removeFileInWorkDir(wstring fileName) {
    wstring path = workPath;
	path.append(L"\\").append(fileName);
    return DeleteFileW(towchar_t(path)) == 0;
}

BOOL makeFileInWorkDir(wstring fileName) {
    wstring path = workPath;
	path.append(L"\\").append(fileName);
    FILE* f = _wfopen(towchar_t(path), L"w+");
    if (f == NULL)
        return false;
    fclose(f);
    return true;
}

BOOL removePidFile() {
    wstring path = workPath;
	path.append(L"\\").append(pidFileName);
    return DeleteFileW(towchar_t(path)) == 0;
}

BOOL makePidFile() {
	removePidFile();

	DWORD wpid = GetCurrentProcessId();
	wstring path = workPath;
	path.append(L"\\").append(pidFileName);
    FILE* f = _wfopen(towchar_t(path), L"w+");
    if (f == NULL)
        return false;
	fwprintf(f, L"%d", wpid);
    fclose(f);
    return true;
}

BOOL existsFile(wstring file) {
    wifstream ifile(towchar_t(file));
    if (ifile!=NULL){
		ifile.close();
		return true;
	}else{
		return false;
	}
}

void processKill() {
    TerminateProcess(piProcessInfo.hProcess, 0);
    removeFileInWorkDir(startFileName);
    removeFileInWorkDir(stopFileName);
}

bool processIsActive() {
	DWORD code;
	if (GetExitCodeProcess(piProcessInfo.hProcess, &code)) {
		if (code == STILL_ACTIVE) {
			return true;
		} else {
			return false;
		}
	} else {
		return false;
	}
}

bool checkUpdate() {
	try{
		wstring fupd=workPath;
		fupd.append(L"\\native\\dwagupd.dll");
		HINSTANCE hinstLib = LoadLibraryW(fupd.c_str());
		if (hinstLib != NULL){
			FCALLBACKLOG FClbk = (FCALLBACKLOG)GetProcAddress(hinstLib, "setCallbackWriteLog");
			if (FClbk!= NULL){
				FClbk(WriteToLog);
			}else{
				WriteToLog(L"ERROR: Updater method setCallbackWriteLog not loaded.");
			}
			FUPDATER FUpd = (FUPDATER) GetProcAddress(hinstLib, "checkUpdate");
			if (FUpd!= NULL){
				bool bret = FUpd();
				if (!FreeLibrary(hinstLib)){
					WriteToLog(L"ERROR: Updater function not unloaded.");
				}
				return bret;
			}else{
				WriteToLog(L"ERROR: Updater method checkUpdate not loaded.");
			}
		}else{
			WriteToLog(L"ERROR: Updater library not loaded.");
		}
	} catch (...) {
		WriteToLog(L"ERROR: Updater library.");
	}
	return false;
}

bool processStart() {
    bool result = false;

	if (!brunonfly){
		if (existsFileInWorkDir(startFileName)) {
			WriteToLog(L"WARNING: Removed start file.");
			removeFileInWorkDir(startFileName);
		}

		if (existsFileInWorkDir(stopFileName)) {
			WriteToLog(L"WARNING: Removed stop file.");
			removeFileInWorkDir(stopFileName);
		}
	}


	wstring args = L"\"";
	args.append(pythonPath);
	args.append(L"\" ").append(parameters);
	wstring apps=L"WorkPath=";
	WriteToLog(apps.append(workPath).c_str());
	apps=L"Command=";
    WriteToLog(apps.append(args).c_str());

    memset(&siStartupInfo, 0, sizeof (siStartupInfo));
    memset(&piProcessInfo, 0, sizeof (piProcessInfo));
    siStartupInfo.cb = sizeof (siStartupInfo);
    siStartupInfo.lpReserved=NULL;
    siStartupInfo.lpDesktop=NULL;
	if (!brunonfly){
		siStartupInfo.lpTitle=L"DWAgentSvc";
	}else{
		siStartupInfo.lpTitle=L"DWAgentRunOnFlySvc";		
	}
    siStartupInfo.dwX=0;
    siStartupInfo.dwY=0;
    siStartupInfo.dwXSize=0;
    siStartupInfo.dwYSize=0;
    siStartupInfo.dwXCountChars=0;
    siStartupInfo.dwYCountChars=0;
    siStartupInfo.dwFillAttribute=0;
	siStartupInfo.wShowWindow = SW_HIDE;
	siStartupInfo.dwFlags = STARTF_USESHOWWINDOW;

	SECURITY_ATTRIBUTES sa = {0};
    sa.nLength = sizeof (SECURITY_ATTRIBUTES);
    sa.bInheritHandle = FALSE;
    sa.lpSecurityDescriptor = NULL;


	HANDLE h = CreateFileW(towchar_t(logfile), GENERIC_WRITE | GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, &sa, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    if (h != INVALID_HANDLE_VALUE) {
        SetFilePointer(h, 0L, NULL, FILE_END);
        siStartupInfo.dwFlags = STARTF_USESTDHANDLES;
        siStartupInfo.hStdOutput = h;
        siStartupInfo.hStdError = h;
        //siStartupInfo.hStdInput = h;
    } else {
		WriteToLog(L"ERROR: Redirect out/err to file");
    }

	if (CreateProcessW(NULL, 
            towchar_t(args), 
            NULL,
            NULL,
            sa.bInheritHandle,
            HIGH_PRIORITY_CLASS | CREATE_NEW_CONSOLE,
            NULL,
            towchar_t(workPath), 
            &siStartupInfo,
            &piProcessInfo) == TRUE) {

		if (!brunonfly){
			//Attende la creazione del file .start
			int cnt = 0;
			while ((cnt <= 20) && (processIsActive()) && (!existsFileInWorkDir(startFileName))) {
				Sleep(2000);
				cnt++;
			}

			if ((processIsActive()) && (existsFileInWorkDir(startFileName))) {
				removeFileInWorkDir(startFileName);
				result = true;
			} else {
				if (!processIsActive()){
					WriteToLog(L"ERROR: Process not Active.");
				}else if (!existsFileInWorkDir(startFileName)){
					WriteToLog(L"ERROR: Missing start file.");
				}
				processKill();
			}
		}else{
			result = true;
		}
    }else{
		wchar_t strmsg[1000];
		wcscpy(strmsg, L"CreateProcess failed ");
		_itow(GetLastError(),strmsg,10);
		wcscat(strmsg, L" .");
		WriteToLog(strmsg);
	}
    return result;
}

void processStop() {
    ServiceStatus.dwWin32ExitCode = 0;
	//Attende l'eliminazione del file .stop
    makeFileInWorkDir(stopFileName);
    int cnt = 0;
    while ((cnt <= 20) && (processIsActive())) {
        Sleep(2000);
        cnt++;
    }
    if (processIsActive()) {
        ServiceStatus.dwWin32ExitCode = 1;
        processKill();
    }
    removeFileInWorkDir(stopFileName);


}

void loadProperties() {
	wstring appfn = workPath;
	appfn.append(L"\\native\\service.properties");
    WriteToLog(L"Reading properties...");
	WriteToLog(appfn.c_str());

    wifstream myfile(towchar_t(appfn));
    if (myfile.is_open()) {
        wstring line;
        while (myfile.good()) {
			getline(myfile, line);

            //Legge le proprietà necessarie
            int endpart1 = line.find_first_of(L"=");
            wstring part1 = line.substr(0, endpart1);
            trimAll(part1);
            wstring part2 = line.substr(endpart1 + 1);
            trimAll(part2);

            if (part1.compare(L"serviceName") == 0) {
                serviceName = part2;
				pidFileName = L"dwagent.pid";
                startFileName = L"dwagent.start";
                stopFileName = L"dwagent.stop";
            }

            if (part1.compare(L"pythonPath") == 0) {
                pythonPath = part2;
            }

            if (part1.compare(L"workPath") == 0) {
                workPath = part2;
            }

            if (part1.compare(L"parameters") == 0) {
                parameters = part2;
            }

        }
        myfile.close();
    } else {
        throw "ERROR: Read properties error.";
    }

    WriteToLog(L"Reading properties.");
}


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

//######################################
//############ INSTALLER ###############
//######################################
wchar_t* towcharp(wstring str) {
	wchar_t*  wc = new wchar_t[str.size() + 1];
	str.copy(wc,str.size());
	wc[str.size()]='\0';
	return wc;
}

vector<wstring> split(const wstring& s, const wstring& delim, const bool keep_empty = true) {
    vector<wstring> result;
    if (delim.empty()) {
        result.push_back(s);
        return result;
    }
    wstring::const_iterator substart = s.begin(), subend;
    while (true) {
        subend = search(substart, s.end(), delim.begin(), delim.end());
        wstring temp(substart, subend);
        if (keep_empty || !temp.empty()) {
            result.push_back(temp);
        }
        if (subend == s.end()) {
            break;
        }
        substart = subend + delim.size();
    }
    return result;
}



void createLink(wchar_t* workPath,wchar_t* dstpath,wchar_t *iconame,wchar_t *command, wchar_t *label){
	//Crea Directory
	CoInitialize(NULL);
	
	//Crea Link
    HRESULT hres = NULL;
	IShellLinkW* pShellLink;
    IPersistFile* pPersistFile;

	hres = CoCreateInstance(CLSID_ShellLink,NULL,CLSCTX_INPROC_SERVER,
                                                        IID_IShellLinkW,
                                                        reinterpret_cast<void**>(&pShellLink));
     if (SUCCEEDED(hres)){
		wchar_t szExePath[_MAX_PATH-1];
		wcscpy(szExePath, workPath);
		wcscat(szExePath, L"\\native\\dwaglnc.exe");
		pShellLink->SetPath(szExePath);

		wchar_t szExeArg[_MAX_PATH-1];
		wcscpy(szExeArg, command);
		pShellLink->SetArguments(szExeArg);

		wchar_t szWorkPath[_MAX_PATH-1];
		wcscpy(szWorkPath, workPath);
		wcscat(szWorkPath, L"\\native");
		pShellLink->SetWorkingDirectory(szWorkPath);

		wchar_t szIconPath[_MAX_PATH-1];
		wcscpy(szIconPath, workPath);
		wcscat(szIconPath, L"\\images\\");
		wcscat(szIconPath, iconame);
		wcscat(szIconPath, L".ico" );
		pShellLink->SetIconLocation(szIconPath,0);

        hres = pShellLink->QueryInterface(IID_IPersistFile, reinterpret_cast<void**>(&pPersistFile));

        if (SUCCEEDED(hres)){
			wchar_t WideCharacterBuffer[_MAX_PATH-1];
			wcscpy(WideCharacterBuffer, dstpath);
			wcscat(WideCharacterBuffer, L"\\");
			wcscat(WideCharacterBuffer, label);
			wcscat(WideCharacterBuffer, L".lnk" );
			hres = pPersistFile->Save(WideCharacterBuffer, TRUE);
			pPersistFile->Release();
        }
        pShellLink->Release();
    }
}

bool installShortcuts(wchar_t* workPath){
	//Crea i link nello start menu
	LPITEMIDLIST pidl;
	HRESULT hr = SHGetSpecialFolderLocation(NULL, CSIDL_COMMON_PROGRAMS, &pidl);
	wchar_t SpecialFolderPath[_MAX_PATH-1];
	BOOL f = SHGetPathFromIDListW(pidl, SpecialFolderPath);
	LPMALLOC pMalloc;
	hr = SHGetMalloc(&pMalloc);
	pMalloc->Free(pidl);
	pMalloc->Release();

	wchar_t myDirectory[_MAX_PATH-1];
	wcscpy(myDirectory, SpecialFolderPath);
	wcscat(myDirectory,L"\\");
	wcscat(myDirectory, L"DWAgent");
    CreateDirectoryW(myDirectory, NULL);
	createLink(workPath,myDirectory, L"logo", L"monitor", L"DWAgent");

	//Crea link in Native
	wchar_t appDirectory[_MAX_PATH-1];
	wcscpy(appDirectory, workPath);
	wcscat(appDirectory,L"\\");
	wcscat(appDirectory, L"native");
	createLink(workPath, appDirectory, L"logo", L"monitor", L"DWAgent");
	createLink(workPath, appDirectory, L"logo", L"configure", L"Configure");
	createLink(workPath, appDirectory, L"logo", L"uninstall", L"Uninstall");
	
	//Crea la voce di registo per l'uninstaller
	HKEY regkey;
	LSTATUS st = RegCreateKeyW(HKEY_LOCAL_MACHINE,L"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\DWAgent", &regkey);
	if (st==ERROR_SUCCESS){

		wchar_t* appdn = L"DWAgent";
		st = RegSetValueExW(regkey, L"DisplayName",0, REG_SZ, (BYTE *)appdn, wcslen(appdn)*2);

		wchar_t iconph[_MAX_PATH-1];
		wcscpy(iconph, workPath);
		wcscat(iconph, L"\\images\\logo.ico");
		st = RegSetValueExW(regkey, L"DisplayIcon",0, REG_SZ, (BYTE *)iconph, wcslen(iconph)*2);


		st = RegSetValueExW(regkey, L"InstallLocation",0, REG_SZ, (BYTE *)workPath, wcslen(workPath)*2);

		wstring path=L"";
		path.append(L"\"").append(workPath).append(L"\\native\\dwaglnc.exe\" uninstall");
		wchar_t* appun = towcharp(path);
		st = RegSetValueExW(regkey, L"UninstallString",0, REG_SZ, (BYTE *)appun, wcslen(appun)*2);

		RegCloseKey(regkey);
	}
	return true;
}

bool removeShortcuts(){
	//Rimuova Directory
	LPITEMIDLIST pidl;
	HRESULT hr = SHGetSpecialFolderLocation(NULL, CSIDL_COMMON_PROGRAMS, &pidl);
	wchar_t SpecialFolderPath[_MAX_PATH-1];
	BOOL f = SHGetPathFromIDListW(pidl, SpecialFolderPath);
	LPMALLOC pMalloc;
	hr = SHGetMalloc(&pMalloc);
	pMalloc->Free(pidl);
	pMalloc->Release();
	wchar_t MyDirectory[_MAX_PATH-1];
	wcscpy(MyDirectory, SpecialFolderPath);
	wcscat(MyDirectory,L"\\DWAgent");

	wchar_t szTemp1[_MAX_PATH-1];
	wcscpy(szTemp1, MyDirectory);
	wcscat(szTemp1, L"\\DWAgent.lnk");
	DeleteFileW(szTemp1);

	RemoveDirectoryW(MyDirectory);

	//Rimuove la voce di registo per l'uninstaller
	HKEY regkey;
	LSTATUS st = RegCreateKeyW(HKEY_LOCAL_MACHINE,L"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall", &regkey);
	if (st==ERROR_SUCCESS){
		RegDeleteKeyW(regkey,L"DWAgent");
		RegCloseKey(regkey);

	}
	return true;
}

bool installAutoRun(wchar_t* name, wchar_t* cmd){
	HKEY regkey;
	LSTATUS st = RegOpenKeyW(HKEY_LOCAL_MACHINE,L"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run", &regkey);
	if (st==ERROR_SUCCESS){
		st = RegSetValueExW(regkey, name,0, REG_SZ, (BYTE *)cmd, wcslen(cmd)*2);
		RegCloseKey(regkey);
	}
	return st==ERROR_SUCCESS;

}

bool removeAutoRun(wchar_t* name){
	HKEY regkey;
	LSTATUS st = RegOpenKeyW(HKEY_LOCAL_MACHINE,L"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run", &regkey);
	if (st==ERROR_SUCCESS){
		st = RegDeleteValueW(regkey,name);
		RegCloseKey(regkey);
	}
	return st==ERROR_SUCCESS;
}

bool enableSoftwareSASGeneration(){
	HKEY regkey;
	LSTATUS st = RegOpenKeyW(HKEY_LOCAL_MACHINE,L"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System", &regkey);
	if (st==ERROR_SUCCESS){
		DWORD value=1;
		st = RegSetValueEx(regkey, "SoftwareSASGeneration",0, REG_DWORD, (const BYTE*)&value, sizeof(value));
		RegCloseKey(regkey);
	}
	return st==ERROR_SUCCESS;
}

bool checkStateService(SC_HANDLE schService,DWORD state){
	SERVICE_STATUS_PROCESS ssp;
    DWORD dwBytesNeeded;
    BOOL bok = QueryServiceStatusEx(
            schService,
            SC_STATUS_PROCESS_INFO,
            (LPBYTE) & ssp,
            sizeof (SERVICE_STATUS_PROCESS),
            &dwBytesNeeded);
    if (bok) {
        if (ssp.dwCurrentState == state) {
            return true;
        }
    }
    return false;
}

bool waitStateService(SC_HANDLE schService,DWORD state){
	int cnt = 0;
    while (cnt <= 30) {
        Sleep(2000);
        SERVICE_STATUS_PROCESS ssp;
        DWORD dwBytesNeeded;
        BOOL bok = QueryServiceStatusEx(
                schService,
                SC_STATUS_PROCESS_INFO,
                (LPBYTE) & ssp,
                sizeof (SERVICE_STATUS_PROCESS),
                &dwBytesNeeded);
        if (bok) {
            if (ssp.dwCurrentState == state) {
                return true;
            }
        } else {
            return false;
        }
        cnt++;
    }
    return false;
}

bool startService(wchar_t* serviceName) {
	bool bret=false;
    SC_HANDLE schSCManager = OpenSCManager(NULL, NULL, SC_MANAGER_CONNECT);
	if (schSCManager){
		SC_HANDLE schService = OpenServiceW(schSCManager, serviceName, SERVICE_START | SERVICE_QUERY_STATUS |  SERVICE_ENUMERATE_DEPENDENTS);
		if (schService){
			if (checkStateService(schService, SERVICE_STOPPED)){
				BOOL bok = StartService(schService, 0, NULL);
				if (bok) {
					bret = waitStateService(schService, SERVICE_RUNNING);
				}
			}
			CloseServiceHandle(schService);
		}
		CloseServiceHandle(schSCManager);
	}
	return bret;
}

bool stopService(wchar_t* serviceName) {
	bool bret=false;
    SC_HANDLE schSCManager = OpenSCManager(NULL, NULL, SC_MANAGER_CONNECT);
	if (schSCManager){
		SC_HANDLE schService = OpenServiceW(schSCManager, serviceName, SERVICE_STOP | SERVICE_QUERY_STATUS |  SERVICE_ENUMERATE_DEPENDENTS);
		if (schService){
			if (checkStateService(schService, SERVICE_RUNNING)){
				SERVICE_STATUS ssStatus;
				BOOL bok = ControlService(schService, SERVICE_CONTROL_STOP, &ssStatus);
				if (bok) {
					bret = waitStateService(schService, SERVICE_STOPPED);
				}
			}
			CloseServiceHandle(schService);
		}
		CloseServiceHandle(schSCManager);
	}
	return bret;
}

bool installService(wchar_t* serviceName, wchar_t* cmd) {
	bool bret=false;
    SC_HANDLE schSCManager = OpenSCManager(NULL, NULL, SC_MANAGER_ALL_ACCESS);
	if (schSCManager){
		SC_HANDLE schService = CreateServiceW(
				schSCManager,
				serviceName,
				serviceName,
				SERVICE_ALL_ACCESS,
				SERVICE_WIN32_OWN_PROCESS,
				SERVICE_AUTO_START,
				SERVICE_ERROR_NORMAL,
				cmd,
				NULL,
				NULL,
				NULL,
				NULL,
				NULL);
		if (schService != NULL) {
			bret = true;
			CloseServiceHandle(schService);
		}		
		CloseServiceHandle(schSCManager);
	}
    return bret;
}


bool deleteService(wchar_t* serviceName) {
	bool bret=false;
    SC_HANDLE schSCManager = OpenSCManager(NULL, NULL, SC_MANAGER_ALL_ACCESS);
	if (schSCManager){
		SC_HANDLE schService = OpenServiceW(schSCManager, serviceName, SC_MANAGER_ALL_ACCESS);
		if (schService != NULL) {
			BOOL bok = DeleteService(schService);
			if (bok) {
				bret = true;
			} else {
				bret = false;
			}
			CloseServiceHandle(schService);
		}
		CloseServiceHandle(schSCManager);
	}
	return bret;
}

bool startRunOnFly(wchar_t* serviceName) {
	bool bret=false;
	SC_HANDLE schSCManager = OpenSCManager(NULL, NULL, SC_MANAGER_ALL_ACCESS);
	if (schSCManager){
		//Elimina vecchio servizia (Se esiste)
		SC_HANDLE schService = OpenServiceW(schSCManager, serviceName, SC_MANAGER_ALL_ACCESS);
		if (schService != NULL) {
			SERVICE_STATUS ssStatus;
			ControlService(schService, SERVICE_CONTROL_STOP, &ssStatus);
			DeleteService(schService);
		}
		CloseServiceHandle(schService);		
		//Crea Servizio
		wstring cmd = L"\"";
		cmd.append(workPath);
		cmd.append(L"\\native\\dwagsvc.exe\" runonfly");
		schService = CreateServiceW(
				schSCManager,
				serviceName,
				serviceName,
				SERVICE_ALL_ACCESS,
				SERVICE_WIN32_OWN_PROCESS,
				SERVICE_DEMAND_START,
				SERVICE_ERROR_NORMAL,
				cmd.c_str(),
				NULL,
				NULL,
				NULL,
				NULL,
				NULL);
		if (schService != NULL) {
			SERVICE_STATUS ssStatus;
			BOOL bok = StartService(schService, 0, NULL);
			if (bok) {
				bret = true;
			}
			ControlService(schService, SERVICE_CONTROL_STOP, &ssStatus);
			DeleteService(schService);
			CloseServiceHandle(schService);
		}
		CloseServiceHandle(schSCManager);
	}
	return bret;
}

int ZZZmain(int argc, char* argv[]) {
	//workPath=L"c:\\programmi\\dwagent";

	 workPath = getDWAgentPath();

	checkUpdate();
	return 0;
}

int main(int argc, char* argv[]) {

    string command = tostr(argv[1]);

    workPath = getDWAgentPath();

    if ((command.compare("run") == 0) || (command.compare("runonfly") == 0)){
        logfile = workPath;
		logfile.append(L"\\native\\service.log");
        //DeleteFileW(towchar_t(logfile));
    }
    try {
        loadProperties();
        if (command.compare("run") == 0) {
			SERVICE_TABLE_ENTRYW ServiceTable[]={{towchar_t(serviceName),ServiceMain},{NULL,NULL}};
			StartServiceCtrlDispatcherW(ServiceTable);
		} else if (command.compare("runonfly") == 0) {
			brunonfly=true;
			SERVICE_TABLE_ENTRYW ServiceTable[]={{towchar_t(serviceName),ServiceMain},{NULL,NULL}};
			StartServiceCtrlDispatcherW(ServiceTable);
		} else if (command.compare("startRunOnFly") == 0) {
			if (startRunOnFly(L"DWAgentRunOnFly")){
				printf("OK");
			}else{
				printf("ERROR");
			}			
		} else if (command.compare("installService") == 0) {
			wstring app = L"\"";
			app.append(workPath);
			app.append(L"\\native\\dwagsvc.exe\" run");
			if (installService(L"DWAgent", towchar_t(app))){
				printf("OK");
			}else{
				printf("ERROR");
			}
		} else if (command.compare("deleteService") == 0) {
			if (deleteService(L"DWAgent")){
				printf("OK");
			}else{
				printf("ERROR");
			}
		} else if (command.compare("startService") == 0) {
			if (startService(L"DWAgent")){
				printf("OK");
			}else{
				printf("ERROR");
			}
		} else if (command.compare("stopService") == 0) {
			if (stopService(L"DWAgent")){
				printf("OK");
			}else{
				printf("ERROR");
			}
		} else if (command.compare("installShortcuts") == 0) {
			if (installShortcuts(towchar_t(workPath))){
				printf("OK");
			}else{
				printf("ERROR");
			}			
		} else if (command.compare("removeShortcuts") == 0) {
			if (removeShortcuts()){
				printf("OK");
			}else{
				printf("ERROR");
			}
		} else if (command.compare("enableSoftwareSASGeneration") == 0) {
			if (enableSoftwareSASGeneration()){
				printf("OK");
			}else{
				printf("ERROR");
			}
		} else if (command.compare("installAutoRun") == 0) {
			wstring app = L"\"";
			app.append(workPath);
			app.append(L"\\native\\dwaglnc.exe\" systray");
			if (installAutoRun(L"DWAgentMon", towchar_t(app))){
				printf("OK");
			}else{
				printf("ERROR");
			}
		} else if (command.compare("removeAutoRun") == 0) {
			if (removeAutoRun(L"DWAgentMon")){
				printf("OK");
			}else{
				printf("ERROR");
			}
		} else {
            printf("ERROR: Unknown command");
        }
    } catch (...) {
        if ((command.compare("run") == 0) || (command.compare("runonfly") == 0)){
            WriteToLog(L"ERROR: Unexpected");
        } else {
            printf("ERROR: Unexpected");
        }
        return 1;
    }
    return 0;
}

void WINAPI ServiceMain(DWORD argc, LPWSTR *argv){
    if (!brunonfly){
		WriteToLog(L"Service starting...");
		makePidFile();
	}

	ServiceStatus.dwServiceType = SERVICE_WIN32;
    ServiceStatus.dwCurrentState = SERVICE_START_PENDING;
    ServiceStatus.dwControlsAccepted = SERVICE_ACCEPT_STOP | SERVICE_ACCEPT_SHUTDOWN;
    ServiceStatus.dwWin32ExitCode = 0;
    ServiceStatus.dwServiceSpecificExitCode = 0;
    ServiceStatus.dwCheckPoint = 0;
    ServiceStatus.dwWaitHint = 0;
    hStatus = RegisterServiceCtrlHandlerW(towchar_t(serviceName),(LPHANDLER_FUNCTION) ServiceCtrlHandler);
    if (hStatus == (SERVICE_STATUS_HANDLE) 0) {
        return;
    }

	if (brunonfly){ //Gli aggiornamenti li fa l'installer
		if (processStart()){
			ServiceStatus.dwCurrentState = SERVICE_RUNNING;
			ServiceStatus.dwCheckPoint = 0;
			ServiceStatus.dwWaitHint = 0;
			SetServiceStatus(hStatus, &ServiceStatus);
			WriteToLog(L"process created.");
			ServiceStatus.dwWin32ExitCode = 0;
		}else{
			WriteToLog(L"process creating error.");
		}
	}else{
		for (int ti=1;ti<=3;ti++){//3 tentativi
			if (processStart()){
				ServiceStatus.dwCurrentState = SERVICE_RUNNING;
				ServiceStatus.dwCheckPoint = 0;
				ServiceStatus.dwWaitHint = 0;
				SetServiceStatus(hStatus, &ServiceStatus);
				WriteToLog(L"Service started.");
				bRunning=true;
				while(bRunning)	{
					if (!processIsActive()){
						WriteToLog(L"Check updating...");
						if (checkUpdate()){
							WriteToLog(L"updated.");
							WriteToLog(L"Process creating...");
							if (processStart()){
								WriteToLog(L"Process created.");
							}else{
								WriteToLog(L"Process creating error.");
							}
						}else{
							WriteToLog(L"Update error.");
						}
					}
					for (int i=1;i<=5;i++){
						if (bRunning){
							Sleep(1000);
						}
					}
				}
				WriteToLog(L"Service stopping...");
				processStop();
				break;
			}else{
				WriteToLog(L"Process creating error.");
				Sleep(3000);
			}
		}
	}
	ServiceStatus.dwCurrentState = SERVICE_STOPPED;
    SetServiceStatus(hStatus, &ServiceStatus);
	
	if (!brunonfly){
		removePidFile();
		WriteToLog(L"Service stopped.");
	}
	return;
}

void WINAPI ServiceCtrlHandler(DWORD Opcode){
    switch (Opcode) {
        case SERVICE_CONTROL_STOP:
            bRunning=false;
			//Wait
			while (ServiceStatus.dwCurrentState == SERVICE_RUNNING) {
				Sleep(100);
			}
			break;
        case SERVICE_CONTROL_SHUTDOWN:
            bRunning=false;
			//Wait
			while (ServiceStatus.dwCurrentState == SERVICE_RUNNING) {
				Sleep(100);
			}
			break;

        default:
            break;
    }
    return;
}

