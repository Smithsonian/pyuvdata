"""Class for reading and writing casa measurement sets."""
"""Requires casacore"""
from astropy import constants as const
import astropy.time as time
import numpy as np
import os
import warnings
from pyuvdata import UVData
import parameter as uvp
import casacore.tables as tables
import telescopes
import re
"""
This dictionary defines the mapping
between CASA polarization numbers and 
AIPS polarization numbers
"""
polDict={1:1,2:2,3:3,4:4,5:-1,6:-3,7:-4,8:-2,9:-5,10:-7,11:-8,12:-6}

#convert from casa stokes integers to pyuvdata
class MS(UVData):
    """
    Defines a class for reading and writing casa measurement sets.
    Attributs:
      ms_required_extra: Names of optional MSParameters that are required for casa ms
    """
    ms_required_extra=['datacolumn','antenna_positions']#,'casa_history']
    def _ms_hist_to_string(self,history_table,test_import_uvfits):
        '''
        converts a CASA history table into a string that can be stored as the uvdata history parameter.
        Also stores messages column as a list for consitency with other uvdata types
        Args: history_table, a casa table object
        test_import_uvfits, true if you are testing .ms file imported from uvfits file by casa. will ignore last five lines of history
        Returns: string containing only message column (consistent with other UVDATA history strings)
                 string enconding complete casa history table converted with \n denoting rows and ';' denoting column breaks
        '''
        message_str=''# string to store usual uvdata history
        history_str='APP_PARAMS;CLI_COMMAND;APPLICATION;MESSAGE;OBJECT_ID;OBSERVATION_ID;ORIGIN;PRIORITY;TIME\n'
        #string to store special casa history
        app_params=history_table.getcol('APP_PARAMS')['array']
        cli_command=history_table.getcol('CLI_COMMAND')['array']
        application=history_table.getcol('APPLICATION')
        message=history_table.getcol('MESSAGE')
        obj_id=history_table.getcol('OBJECT_ID')
        obs_id=history_table.getcol('OBSERVATION_ID')
        origin=history_table.getcol('ORIGIN')
        priority=history_table.getcol('PRIORITY')
        times=history_table.getcol('TIME')
        #Now loop through columns and generate history string
        ntimes=len(times)
        if test_import_uvfits:
            ntimes-=5
        for tbrow in range(ntimes):
            message_str+=str(message[tbrow])
            newline=str(app_params[tbrow]) \
            +';'+str(cli_command[tbrow]) \
            +';'+str(application[tbrow]) \
            +';'+str(message[tbrow]) \
            +';'+str(obj_id[tbrow]) \
            +';'+str(obs_id[tbrow]) \
            +';'+str(origin[tbrow]) \
            +';'+str(priority[tbrow]) \
            +';'+str(times[tbrow])+'\n'
            history_str+=newline
            if tbrow<ntimes-1:
                message_str+='\n'
        def is_not_ascii(s):
            return any(ord(c) >= 128 for c in s)
        def find_not_ascii(s):
            output=[]
            for c in s:
                if ord(c)>=128:
                    output+=c
            return output
        #!--Lines Added for Testing!
        #print('not ascii:')
        #print len(find_not_ascii(history_str))
        #print(find_not_ascii(history_str))
        #print 'decoded\n'
        #print history_str.decode('ascii')
        #print 'decoded\n'
        #_ascii_text_re = re.compile(r'[ -~]*\Z')
        
        #print _ascii_text_re.match(history_str)
        #!--End Testing!
        return message_str,history_str


    
    #ms write functionality to be added later. 
    def write_ms(self):
        '''
        writing ms is not yet supported
        '''
    
    def read_ms(self,filepath,run_check=True,run_check_acceptability=True,data_column='DATA',pol_order='AIPS',test_import_uvfits=False):
        '''
        read in a casa measurement set
        ARGS:
        filepath: name of the measurement set folder
        run_check:specify whether you want to run check
        run_check_acceptability: run acceptability check for new UVData object
        data_column: specify which CASA measurement set data column to read from (can be 'DATA','CORRECTED', or 'MODEL')
        pol_order: use 'AIPS' or 'CASA' ordering of polarizations?
        test_import_uvfits: test a .ms file that was created with CASA importuvfits method: 
        ignores last five lines of history which contain information on importuvfits command. 
        '''
        #make sure user requests a valid data_column
        if data_column!='DATA' and data_column!='CORRECTED_DATA' and data_column!='MODEL':
            raise ValueError('Invalid data_column value supplied. Use \'Data\',\'MODEL\' or \'CORRECTED_DATA\'')
        if not os.path.exists(filepath):
            raise(IOError, filepath + ' not found')
        #set visibility units
        if(data_column=='DATA'):
            self.vis_units="UNCALIB"
        elif(data_column=='CORRECTED_DATA'):
            self.vis_units="JY"
        elif(data_column=='MODEL'):
            self.vis_units="JY"
        self.extra_keywords['data_column']=data_column
        #get frequency information from spectral window table
        tb_spws=tables.table(filepath+'/SPECTRAL_WINDOW')
        freqs=tb_spws.getcol('CHAN_FREQ')
        self.freq_array=freqs
        self.Nfreqs=int(freqs.shape[1])
        self.channel_width=float(tb_spws.getcol('CHAN_WIDTH')[0,0])
        self.Nspws=int(freqs.shape[0])
        self.spw_array=np.arange(self.Nspws)
        tb_spws.close()
        #now get the data
        tb=tables.table(filepath)
        #check for multiple subarrays. importuvfits does not appear to preserve subarray information!
        subarray=np.unique(np.int32(tb.getcol('ARRAY_ID'))-1)
        if len(set(subarray))>1:
            raise ValueError('This file appears to have multiple subarray '
                             'values; only files with one subarray are '
                             'supported.')
        times_unique=time.Time(np.unique(tb.getcol('TIME')/(3600.*24.)),format='mjd').jd
        self.Ntimes=int(len(times_unique))
        data_array=tb.getcol(data_column)
        self.Nblts=int(data_array.shape[0])
        flag_array=tb.getcol('FLAG')
        #CASA stores data in complex array with dimension NbltsxNfreqsxNpols
        #-!-What about multiple spws?-!-
        if(len(data_array.shape)==3):
            data_array=np.expand_dims(data_array,axis=1)
            flag_array=np.expand_dims(flag_array,axis=1)
        self.data_array=data_array
        self.flag_array=flag_array
        self.Npols=int(data_array.shape[-1])
        self.uvw_array=tb.getcol('UVW')
        self.ant_1_array=tb.getcol('ANTENNA1').astype(np.int32)
        self.ant_2_array=tb.getcol('ANTENNA2').astype(np.int32)
        self.Nants_data=len(np.unique(np.concatenate((np.unique(self.ant_1_array),np.unique(self.ant_2_array)))))
        self.baseline_array=self.antnums_to_baseline(self.ant_1_array,self.ant_2_array)
        self.Nbls=len(np.unique(self.baseline_array))
        #Get times. MS from cotter are modified Julian dates in seconds (thanks to Danny Jacobs for figuring out the proper conversion)
        self.time_array=time.Time(tb.getcol('TIME')/(3600.*24.),format='mjd').jd
        #Polarization array
        tbPol=tables.table(filepath+'/POLARIZATION')
        polList=tbPol.getcol('CORR_TYPE')[0]#list of lists, probably with each list corresponding to SPW. 
        self.polarization_array=np.zeros(len(polList),dtype=np.int32)
        for polnum in range(len(polList)):
            self.polarization_array[polnum]=int(polDict[polList[polnum]])
        tbPol.close()
        #Integration time
        #use first interval and assume rest are constant (though measurement set has all integration times for each Nblt )
        #self.integration_time=tb.getcol('INTERVAL')[0]
        #for some reason, interval ends up larger than the difference between times...
        self.integration_time=float(times_unique[1]-times_unique[0])*3600.*24.
        #open table with antenna location information
        tbAnt=tables.table(filepath+'/ANTENNA')
        tbObs=tables.table(filepath+'/OBSERVATION')
        self.telescope_name=tbObs.getcol('TELESCOPE_NAME')[0]
        self.instrument=tbObs.getcol('TELESCOPE_NAME')[0]
        tbObs.close()
        #Use Telescopes.py dictionary to set array position
        self.antenna_positions=tbAnt.getcol('POSITION')
        xyz_telescope_frame = tbAnt.getcolkeyword('POSITION','MEASINFO')['Ref']
        antFlags=np.empty(len(self.antenna_positions),dtype=bool)
        antFlags[:]=False
        for antnum in range(len(antFlags)):
            antFlags[antnum]=np.all(self.antenna_positions[antnum,:]==0)
        try:
            self.set_telescope_params()
        except:
            if(xyz_telescope_frame=='ITRF'):
                self.telescope_location=np.array(np.mean(self.antenna_positions[np.invert(antFlags),:],axis=0))
                #antenna names
        ant_names=tbAnt.getcol('STATION')
        self.Nants_telescope=len(antFlags[np.invert(antFlags)])
        test_name=ant_names[0]
        names_same=True
        for antnum in range(len(ant_names)):
            if(not(ant_names[antnum]==test_name)):
                names_same=False
        if(not(names_same)):
            self.antenna_names=ant_names#cotter measurement sets store antenna names in the NAMES column. 
        else:
            self.antenna_names=tbAnt.getcol('NAME')#importuvfits measurement sets store antenna namesin the STATION column.
        self.antenna_numbers=np.arange(len(self.antenna_names)).astype(int)
        nAntOrig=len(self.antenna_names)
        ant_names=[]
        for antNum in range(len(self.antenna_names)):
            if not(antFlags[antNum]):
                ant_names.append(self.antenna_names[antNum])
        self.antenna_names=ant_names
        self.antenna_numbers=self.antenna_numbers[np.invert(antFlags)]
        self.antenna_positions=self.antenna_positions[np.invert(antFlags),:]
        '''
        #remove blank names
        for axnum in range(self.antenna_positions.shape[1]):
            self.antenna_positions[:,axnum]-=np.mean(self.antenna_positions[:,axnum])
        try:
            thisTelescope=telescopes.get_telescope(self.instrument)
            self.telescope_location_lat_lon_alt_degrees=(np.degrees(thisTelescope['latitude']),np.degrees(thisTelescope['longitude']),thisTelescope['altitude'])
            #self.telescope_location=np.array(np.mean(tbAnt.getcol('POSITION'),axis=0))
            print 'Telescope %s is known. Using stored values.'%(self.instrument)
        except:
            #If Telescope is unknown, use mean ITRF Positions of antennas
            self.telescope_location=np.array(np.mean(tbAnt.getcol('POSITION'),axis=0))
        '''
        tbAnt.close()
        tbField=tables.table(filepath+'/FIELD')
        if(tbField.getcol('PHASE_DIR').shape[1]==2):
            self.phase_type='drift'
            self.set_drift()
        elif(tbField.getcol('PHASE_DIR').shape[1]==1):
            self.phase_type='phased'
            self.phase_center_epoch=float(tb.getcolkeyword('UVW','MEASINFO')['Ref'][1:])#MSv2.0 appears to assume J2000. Not sure how to specifiy otherwise
            self.phase_center_ra=float(tbField.getcol('PHASE_DIR')[0][0][0])
            self.phase_center_dec=float(tbField.getcol('PHASE_DIR')[0][0][1])
            self.set_phased()
        #set LST array from times and itrf
        self.set_lsts_from_time_array()

        #set the history parameter
        #as a string with \t indicating column breaks
        #\n indicating row breaks.
        #self.history,self.casa_history=self._ms_hist_to_string(tables.table(filepath+'/HISTORY'),test_import_uvfits)
        _,self.history=self._ms_hist_to_string(tables.table(filepath+'/HISTORY'),test_import_uvfits)      
        #CASA weights column keeps track of number of data points averaged.

        if self.pyuvdata_version_str not in self.history.replace('\n', ''):
            self.history += self.pyuvdata_version_str
        self.nsample_array=tb.getcol('WEIGHT_SPECTRUM')
        if(len(self.nsample_array.shape)==3):
            self.nsample_array=np.expand_dims(self.nsample_array,axis=1)
        self.object_name=tbField.getcol('NAME')[0]
        tbField.close()
        tb.close()
        #order polarizations
        self.order_pols(pol_order)
        if run_check:
            self.check(run_check_acceptability=run_check_acceptability)
